/**
 * Copy Markdown Button Handler
 *
 * Overrides the llmstxt-md plugin's inline async copyMarkdownToClipboard()
 * with a synchronous version that works reliably across browsers.
 *
 * The plugin's async version breaks because await fetch() consumes the
 * transient user activation, causing navigator.clipboard.writeText() to
 * fail. This script pre-fetches markdown and copies synchronously via
 * execCommand, preserving the user gesture chain.
 *
 * Subscribes to MkDocs Material's document$ observable (a ReplaySubject(1))
 * so it re-initializes on every instant navigation, always overriding the
 * plugin's inline script.
 */
(function() {
    'use strict';

    // Constants
    const FEEDBACK_DURATION_MS = 2000;
    const IOS_MAX_SELECTION = 999999;

    // Module state
    let cachedMarkdown = null;
    let fetchError = null;
    let abortController = null;

    /**
     * Returns the expected markdown path for the current page URL.
     *
     * @returns {string} Absolute path to the .md file (e.g. "/site/page/index.md")
     */
    function getCurrentMdPath() {
        const currentPath = window.location.pathname;
        return currentPath.endsWith('/')
            ? currentPath + 'index.md'
            : currentPath.replace(/\.html$/, '.md');
    }

    /**
     * Restores the copy button visibility (reverses any prior hideButton call).
     *
     * @returns {void}
     */
    function showButton() {
        const button = document.getElementById('llms-copy-button');
        if (button) {
            button.style.display = '';
        }
    }

    /**
     * Hides the copy button when markdown content is unavailable.
     *
     * @returns {void}
     */
    function hideButton() {
        const button = document.getElementById('llms-copy-button');
        if (button) {
            button.style.display = 'none';
        }
    }

    /**
     * Fetches markdown for the current page and caches it.
     * Cancels any in-flight request via AbortController to prevent stale
     * content from a previous navigation overwriting the cache.
     *
     * @returns {void}
     */
    function prefetchMarkdown() {
        if (abortController) {
            abortController.abort();
        }
        abortController = new AbortController();

        cachedMarkdown = null;
        fetchError = null;

        const mdPath = getCurrentMdPath();

        fetch(mdPath, { signal: abortController.signal })
            .then(response => {
                if (!response.ok) throw new Error('Not found');
                return response.text();
            })
            .then(text => {
                cachedMarkdown = text
                    .replace(/[\r\n]*Copy Markdown[\r\n\s]*$/i, '')
                    .replace(/\s+$/, '');
            })
            .catch(err => {
                if (err.name === 'AbortError') return;
                fetchError = err;
                console.warn('Could not prefetch markdown:', err);
                hideButton();
            });
    }

    /**
     * Copies text to clipboard using execCommand.
     *
     * We use execCommand instead of navigator.clipboard.writeText() because
     * the Clipboard API requires the operation to be within a live user
     * gesture. Any preceding await (e.g. await fetch()) consumes the
     * transient activation, causing writeText() to throw. execCommand is
     * synchronous, so it works reliably when content is pre-fetched.
     *
     * @param {string} text - Text to copy to clipboard
     * @returns {boolean} Whether the copy succeeded
     */
    function copyToClipboard(text) {
        const textarea = document.createElement('textarea');
        textarea.value = text;

        textarea.style.cssText = 'position:fixed;top:0;left:0;width:2em;height:2em;padding:0;border:none;outline:none;box-shadow:none;background:transparent;';

        document.body.appendChild(textarea);

        if (/ipad|iphone/i.test(navigator.userAgent)) {
            textarea.contentEditable = 'true';
            textarea.readOnly = false;

            const range = document.createRange();
            range.selectNodeContents(textarea);

            const selection = window.getSelection();
            selection.removeAllRanges();
            selection.addRange(range);
            textarea.setSelectionRange(0, IOS_MAX_SELECTION);
        } else {
            textarea.focus();
            textarea.select();
        }

        let success = false;
        try {
            success = document.execCommand('copy');
        } catch (err) {
            console.error('execCommand error:', err);
        }

        document.body.removeChild(textarea);
        return success;
    }

    /**
     * Shows success feedback on the button.
     *
     * @param {HTMLElement} button - The button element
     * @returns {void}
     */
    function showSuccess(button) {
        const originalHTML = button.innerHTML;
        button.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><polyline points="20 6 9 17 4 12"></polyline></svg>Copied!';
        button.classList.add('success');
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('success');
        }, FEEDBACK_DURATION_MS);
    }

    /**
     * Shows error feedback on the button.
     *
     * @param {HTMLElement} button - The button element
     * @param {string} message - Error message to log
     * @returns {void}
     */
    function showError(button, message) {
        console.error('Copy failed:', message);
        const originalHTML = button.innerHTML;
        button.innerHTML = '<svg xmlns="http://www.w3.org/2000/svg" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" stroke-width="2" stroke-linecap="round" stroke-linejoin="round" style="margin-right:6px"><circle cx="12" cy="12" r="10"></circle><line x1="15" y1="9" x2="9" y2="15"></line><line x1="9" y1="9" x2="15" y2="15"></line></svg>Failed';
        button.classList.add('error');
        setTimeout(() => {
            button.innerHTML = originalHTML;
            button.classList.remove('error');
        }, FEEDBACK_DURATION_MS);
    }

    /**
     * Synchronous copy handler. Assigned to window.copyMarkdownToClipboard
     * to override the plugin's broken async version.
     *
     * @returns {void}
     */
    function handleCopy() {
        const button = document.querySelector('#llms-copy-button button');
        if (!button) {
            console.warn('Copy button not found');
            return;
        }

        if (fetchError || !cachedMarkdown) {
            showError(button, 'Markdown not available');
            return;
        }

        const success = copyToClipboard(cachedMarkdown);

        if (success) {
            showSuccess(button);
        } else {
            showError(button, 'Copy failed');
        }
    }

    /**
     * Initializes the copy handler for the current page:
     * - Restores button visibility (in case a prior page hid it)
     * - Cancels any in-flight fetch and pre-fetches current page's markdown
     * - Overrides the plugin's inline async function with our sync version
     *
     * @returns {void}
     */
    function initialize() {
        showButton();
        prefetchMarkdown();
        window.copyMarkdownToClipboard = handleCopy;
    }

    // document$ is a ReplaySubject(1) — it emits the current document
    // immediately on subscribe, so a single subscription handles both the
    // initial page load and all subsequent instant navigations.
    if (typeof document$ !== 'undefined') {
        document$.subscribe(() => {
            initialize();
        });
    } else {
        initialize();
    }
})();

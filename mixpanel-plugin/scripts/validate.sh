#!/usr/bin/env bash
set -euo pipefail

# Plugin structure validation script
# Validates JSON schema, YAML frontmatter, and file structure

PLUGIN_DIR="${1:-.}"
ERRORS=0

echo "🔍 Validating plugin structure in: $PLUGIN_DIR"
echo ""

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
NC='\033[0m' # No Color

pass() {
    echo -e "${GREEN}✓${NC} $1"
}

fail() {
    echo -e "${RED}✗${NC} $1"
    ((ERRORS++))
}

warn() {
    echo -e "${YELLOW}⚠${NC} $1"
}

# 1. Validate JSON files
echo "📋 Validating JSON files..."
for json_file in "$PLUGIN_DIR/.claude-plugin/plugin.json" "$PLUGIN_DIR/.claude-plugin/marketplace.json"; do
    if [[ -f "$json_file" ]]; then
        if jq . "$json_file" > /dev/null 2>&1; then
            pass "Valid JSON: $(basename "$json_file")"
        else
            fail "Invalid JSON: $json_file"
        fi
    else
        warn "Missing JSON: $json_file"
    fi
done
echo ""

# 2. Validate command frontmatter (YAML)
echo "📝 Validating command frontmatter..."
if [[ -d "$PLUGIN_DIR/commands" ]]; then
    for cmd_file in "$PLUGIN_DIR/commands"/*.md; do
        if [[ -f "$cmd_file" ]]; then
            # Extract frontmatter (between --- markers)
            if grep -q "^---$" "$cmd_file"; then
                # Check if frontmatter has required fields
                frontmatter=$(sed -n '/^---$/,/^---$/p' "$cmd_file" | head -n -1 | tail -n +2)

                # Check for required fields
                has_description=$(echo "$frontmatter" | grep -c "^description:" || true)
                has_allowed_tools=$(echo "$frontmatter" | grep -c "^allowed-tools:" || true)

                if [[ $has_description -gt 0 && $has_allowed_tools -gt 0 ]]; then
                    pass "Valid frontmatter: $(basename "$cmd_file")"
                else
                    fail "Missing required fields in: $(basename "$cmd_file")"
                    [[ $has_description -eq 0 ]] && echo "    - Missing 'description'"
                    [[ $has_allowed_tools -eq 0 ]] && echo "    - Missing 'allowed-tools'"
                fi
            else
                fail "No frontmatter in: $(basename "$cmd_file")"
            fi
        fi
    done
else
    warn "No commands/ directory found"
fi
echo ""

# 3. Validate reference files are non-empty
echo "📚 Validating reference files..."
if [[ -d "$PLUGIN_DIR/skills" ]]; then
    for ref_dir in "$PLUGIN_DIR/skills"/*/references; do
        if [[ -d "$ref_dir" ]]; then
            for ref_file in "$ref_dir"/*.md; do
                if [[ -f "$ref_file" ]]; then
                    size=$(wc -c < "$ref_file")
                    if [[ $size -gt 0 ]]; then
                        pass "Non-empty reference: $(basename "$ref_file") ($size bytes)"
                    else
                        fail "Empty reference file: $ref_file"
                    fi
                fi
            done
        fi
    done
else
    warn "No skills/ directory found"
fi
echo ""

# 4. Validate directory structure
echo "📁 Validating directory structure..."
expected_dirs=(".claude-plugin" "commands")
for dir in "${expected_dirs[@]}"; do
    if [[ -d "$PLUGIN_DIR/$dir" ]]; then
        pass "Directory exists: $dir/"
    else
        fail "Missing directory: $dir/"
    fi
done
echo ""

# 5. Validate plugin manifest fields
echo "🔧 Validating plugin manifest..."
if [[ -f "$PLUGIN_DIR/.claude-plugin/plugin.json" ]]; then
    required_fields=("name" "version" "description")
    for field in "${required_fields[@]}"; do
        value=$(jq -r ".$field // empty" "$PLUGIN_DIR/.claude-plugin/plugin.json")
        if [[ -n "$value" ]]; then
            pass "Required field '$field': $value"
        else
            fail "Missing required field: $field"
        fi
    done
else
    fail "plugin.json not found"
fi
echo ""

# 6. Check for common issues
echo "🔍 Checking for common issues..."

# Check for duplicate command names
if [[ -d "$PLUGIN_DIR/commands" ]]; then
    duplicates=$(find "$PLUGIN_DIR/commands" -name "*.md" -exec basename {} \; | sort | uniq -d)
    if [[ -z "$duplicates" ]]; then
        pass "No duplicate command names"
    else
        fail "Duplicate command names found:"
        echo "$duplicates"
    fi
fi

# Check that all commands use allowed-tools (security)
if [[ -d "$PLUGIN_DIR/commands" ]]; then
    commands_without_allowed_tools=$(grep -L "^allowed-tools:" "$PLUGIN_DIR/commands"/*.md 2>/dev/null || true)
    if [[ -z "$commands_without_allowed_tools" ]]; then
        pass "All commands specify allowed-tools"
    else
        fail "Commands missing allowed-tools:"
        echo "$commands_without_allowed_tools"
    fi
fi

echo ""
echo "========================================="
if [[ $ERRORS -eq 0 ]]; then
    echo -e "${GREEN}✓ Validation passed!${NC} No errors found."
    exit 0
else
    echo -e "${RED}✗ Validation failed!${NC} Found $ERRORS error(s)."
    exit 1
fi

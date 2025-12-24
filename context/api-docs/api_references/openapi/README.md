# OpenAPI Specification

To learn more details please visit the living [Notion Doc](https://www.notion.so/mpspeed/OpenAPI-Specification-544cbb6f5f3c438babeebff12960810c)

## Commands

### Lint

lint spec templates in `/src`

```
npm run lint:api-refs
```

### Bundle

bundle spec from `/src` and output to `out`

```
npm run build:api-refs
```

### Publish

publishes the bundled spec files in `out/specname.openapi.yaml` to our readme.com project.

If a specname is not provided it will go through it file in `/out`.

```
VERSION=readme_version_id npm run publish:api-refs [specname]
```

_This currently requires interacting with readme's CLI. It is currently a wrapper to help with authentication and versioning._

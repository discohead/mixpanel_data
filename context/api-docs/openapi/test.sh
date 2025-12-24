#!/bin/bash

set -e

npm run api:lint
npm run api:build
for file in openapi/out/*.json; do
  echo "✔ Validating $file"
  npx rdme openapi:validate $file
done

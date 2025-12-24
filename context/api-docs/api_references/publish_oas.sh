#!/bin/bash

# https://docs.readme.com/docs/openapi-compatibility-chart
# https://github.com/OAI/OpenAPI-Specification

# "npm run rdme login" to prevent needing keys for every command

# TODO auto create versions
# echo $(npm run rdme versions --raw) | sed 's/.*\[\(.*\)\].*/\[\1\]/' | jq -c '.[] | select(.is_stable)'


VERSION="${VERSION:? missing version env var}"
if ! [[ $VERSION =~ ^v?[23] ]]; then
  echo 'You can only publish to versions > 2.0';
  exit 1;
fi

FILEMATCH=${1:-*}

ran=0
for file in $(find api_references/openapi/out -type f -not -name "*.internal.openapi.yaml" -name "$FILEMATCH.openapi.yaml")
  do
    ran=1;
    read -p "publish $file to version $VERSION? <y/N>: " prompt
    if [[ $prompt == "y" ]]; then
      npm run rdme openapi:validate $file
      npm run rdme openapi --version=$VERSION $file
    fi
done

if [[ $ran == 0 ]]; then
  echo No file matching $1
fi

#!/bin/bash

# Common assertion function for bats tests
# Usage: assert expected_value received_value
assert() {
    if [ $# -ne 2 ]; then
        echo "Error: assert requires exactly 2 arguments, but $# were provided." >&2
        return 1
    fi

    local expected="$1"
    local received="$2"

    if [ "$expected" != "$received" ]; then
        echo "Assertion failed!" >&2
        echo "  Expected: \"$expected\"" >&2
        echo "  Received: \"$received\"" >&2
        return 1
    fi
}

export -f assert

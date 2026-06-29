#!/bin/bash

# This mock expects a variable CMDLINE to be set, containing the simulated kernel command line.
getcmdline() {
    echo $CMDLINE
}

debug_off() {
    :
}

debug_on() {
    :
}

warn() {
    :
}

dracut-getarg() {
    tests/mocks/dracut-getarg $@
}

# verbatim copy of dracut functions from dracut-059+suse.787.gfb86123e-1.1.x86_64
getarg() {
    debug_off
    local _deprecated _newoption
    CMDLINE=$(getcmdline)
    export CMDLINE
    while [ $# -gt 0 ]; do
        case $1 in
            -d)
                _deprecated=1
                shift
                ;;
            -y)
                if dracut-getarg "$2" > /dev/null; then
                    if [ "$_deprecated" = "1" ]; then
                        if [ -n "$_newoption" ]; then
                            warn "Kernel command line option '$2' is deprecated, use '$_newoption' instead."
                        else
                            warn "Option '$2' is deprecated."
                        fi
                    fi
                    echo 1
                    debug_on
                    return 0
                fi
                _deprecated=0
                shift 2
                ;;
            -n)
                if dracut-getarg "$2" > /dev/null; then
                    echo 0
                    if [ "$_deprecated" = "1" ]; then
                        if [ -n "$_newoption" ]; then
                            warn "Kernel command line option '$2' is deprecated, use '$_newoption=0' instead."
                        else
                            warn "Option '$2' is deprecated."
                        fi
                    fi
                    debug_on
                    return 1
                fi
                _deprecated=0
                shift 2
                ;;
            *)
                if [ -z "$_newoption" ]; then
                    _newoption="$1"
                fi
                if dracut-getarg "$1"; then
                    if [ "$_deprecated" = "1" ]; then
                        if [ -n "$_newoption" ]; then
                            warn "Kernel command line option '$1' is deprecated, use '$_newoption' instead."
                        else
                            warn "Option '$1' is deprecated."
                        fi
                    fi
                    debug_on
                    return 0
                fi
                _deprecated=0
                shift
                ;;
        esac
    done
    debug_on
    return 1
}

# getargbool <defaultval> <args...>
# False if "getarg <args...>" returns "0", "no", or "off".
# True if getarg returns any other non-empty string.
# If not found, assumes <defaultval> - usually 0 for false, 1 for true.
# example: getargbool 0 rd.info
#   true: rd.info, rd.info=1, rd.info=xxx
#   false: rd.info=0, rd.info=off, rd.info not present (default val is 0)
getargbool() {
    local _b
    unset _b
    local _default
    _default="$1"
    shift
    _b=$(getarg "$@") || _b=${_b:-"$_default"}
    if [ -n "$_b" ]; then
        [ "$_b" = "0" ] && return 1
        [ "$_b" = "no" ] && return 1
        [ "$_b" = "off" ] && return 1
    fi
    return 0
}

isdigit() {
    case "$1" in
        *[!0-9]* | "") return 1 ;;
    esac

    return 0
}

# getargnum <defaultval> <minval> <maxval> <arg>
# Will echo the arg if it's in range [minval - maxval].
# If it's not set or it's not valid, will set it <defaultval>.
# Note all values are required to be >= 0 here.
# <defaultval> should be with [minval -maxval].
getargnum() {
    local _b
    unset _b
    local _default _min _max
    _default="$1"
    shift
    _min="$1"
    shift
    _max="$1"
    shift
    _b=$(getarg "$1") || _b=${_b:-"$_default"}
    if [ -n "$_b" ]; then
        isdigit "$_b" && _b=$((_b)) \
            && [ $_b -ge "$_min" ] && [ $_b -le "$_max" ] && echo $_b && return
    fi
    echo "$_default"
}

# replaces all occurrences of 'search' in 'str' with 'replacement'
#
# str_replace str search replacement
#
# example:
# str_replace '  one two  three  ' ' ' '_'
str_replace() {
    local in="$1"
    local s="$2"
    local r="$3"
    local out=''

    while [ "${in##*"$s"*}" != "$in" ]; do
        chop="${in%%"$s"*}"
        out="${out}${chop}$r"
        in="${in#*"$s"}"
    done
    printf -- '%s' "${out}${in}"
}
# EOF verbatim copy

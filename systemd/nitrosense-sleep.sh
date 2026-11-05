#!/bin/sh
case "$1/$2" in
  post/*)
    /usr/local/bin/nitrosense apply-saved >/dev/null 2>&1
    ;;
esac

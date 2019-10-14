#!/bin/bash

cat /tmp/wpa_supplicant_*.pid | while read PID ; do
    kill $PID
done


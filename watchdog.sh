#!/bin/bash
while true; do
    if ! pgrep -f extract_sar_scenes.py > /dev/null; then
        echo "$(date): Restarting extraction..."
        nohup python3 extract_sar_scenes.py >> sar_scenes_log.txt 2>&1 &
    fi
    sleep 60
done

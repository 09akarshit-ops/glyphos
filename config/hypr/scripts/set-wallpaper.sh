#!/bin/bash
pkill hyprpaper 2>/dev/null
sleep 1
hyprpaper &
for i in $(seq 1 10); do
    sleep 1
    hyprctl hyprpaper preload ~/Pictures/wallpaper.jpg 2>/dev/null
    if hyprctl hyprpaper wallpaper "LVDS-1,~/Pictures/wallpaper.jpg" 2>/dev/null; then
        exit 0
    fi
done

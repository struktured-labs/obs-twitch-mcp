#!/bin/bash
# Run this in a terminal to start the PNGtuber audio monitor

cd "$(dirname "$0")"

echo "Starting HTTP server for assets..."
python3 -m http.server 8765 -d assets &
HTTP_PID=$!

echo "Starting audio monitor..."
echo "Speak into your mic to test!"
echo ""

# Simple audio monitor using pacat (PulseAudio)
cleanup() {
    kill $HTTP_PID 2>/dev/null
    exit 0
}
trap cleanup INT TERM

# Use parec to capture audio and calculate levels
while true; do
    # Get 0.1 seconds of audio and calculate RMS volume
    vol=$(timeout 0.1 pacat --record --raw --format=s16le --channels=1 --rate=44100 2>/dev/null | \
          od -An -td2 | tr -s ' \n' '\n' | awk '{sum+=$1*$1; n++} END {if(n>0) printf "%.1f", sqrt(sum/n)/100; else print "0"}')

    echo "{\"volume\": ${vol:-0}, \"timestamp\": $(date +%s.%N)}" > assets/audio-levels.json
done

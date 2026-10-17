cd ~/DeckControl/dist
(./DeckControl.app/Contents/MacOS/DeckControl --no-browser > /tmp/app_run.log 2>&1 &)
sleep 8
echo "--- alive?"; pgrep -x DeckControl || echo "NOT RUNNING"
echo "--- log:"; tail -30 /tmp/app_run.log
echo "--- data log:"; cat ~/DeckControl/dist/DeckControl-data/deckcontrol.log 2>/dev/null | tail
ls ~/Library/Logs/DiagnosticReports 2>/dev/null | grep -i deckcontrol | tail -3
pkill -x DeckControl

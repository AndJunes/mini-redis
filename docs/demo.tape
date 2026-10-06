# Record with: vhs docs/demo.tape

Output docs/demo.gif

Set Shell "bash"
Set FontSize 18
Set Width 1200
Set Height 720
Set Padding 24
Set Theme "Catppuccin Mocha"
Set TypingSpeed 40ms

Hide
Type "export PS1='> ' && rm -f demo.aof && clear"
Enter
Show

Type "# start the server with persistence"
Enter
Type "./run.sh --aof demo.aof & sleep 1"
Enter
Sleep 2s

Type "redis-cli PING"
Enter
Sleep 500ms
Type "redis-cli SET name Andrea"
Enter
Sleep 500ms
Type "redis-cli GET name"
Enter
Sleep 500ms
Type "redis-cli INCR visits"
Enter
Sleep 400ms
Type "redis-cli INCR visits"
Enter
Sleep 1.5s
Screenshot docs/demo-commands.png
Sleep 500ms

Type "clear"
Enter
Type "# keys can expire"
Enter
Type "redis-cli SET session abc123 EX 5"
Enter
Sleep 300ms
Type@15ms "redis-cli TTL session"
Enter
Sleep 500ms
Type "sleep 5; redis-cli GET session"
Enter
Sleep 6s
Screenshot docs/demo-expiry.png
Sleep 500ms

Type "clear"
Enter
Type "# kill the server without a clean shutdown"
Enter
Type "kill -9 %1; sleep 0.5"
Enter
Sleep 1s
Type "./run.sh --aof demo.aof & sleep 1"
Enter
Sleep 2s
Type "redis-cli GET name"
Enter
Sleep 500ms
Type "redis-cli GET visits"
Enter
Sleep 2s
Screenshot docs/demo-recovery.png
Sleep 500ms

Type "clear"
Enter
Type "uv run pytest -q"
Enter
Sleep 4s
Screenshot docs/demo-tests.png
Sleep 1.5s

Hide
Type "kill %1; rm -f demo.aof"
Enter

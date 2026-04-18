# Shell Basics

Use comandos explicitos e seguros.

- Para listar logs: `ls -lah logs`
- Para seguir um log: `tail -f logs/orchestrator.log`
- Para checar uma porta: `lsof -nP -iTCP:6006 -sTCP:LISTEN`
- Para ver containers ativos: `docker ps`
- Para ver sessoes tmux: `tmux list-panes -a -F '#{session_name} dead=#{pane_dead} cmd=#{pane_current_command} pid=#{pane_pid}'`

Evite comandos destrutivos sem validacao previa.

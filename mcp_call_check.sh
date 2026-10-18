#!/bin/bash
# Usage: mcp_call_check.sh <url> <tool> '<json args>'  - one streamable-http MCP tool call
U=$1; T=$2; A=$3
H=(-s -m 300 -H 'Content-Type: application/json' -H 'Accept: application/json, text/event-stream')
SID=$(curl "${H[@]}" -D - -o /dev/null $U -d '{"jsonrpc":"2.0","id":1,"method":"initialize","params":{"protocolVersion":"2025-03-26","capabilities":{},"clientInfo":{"name":"check","version":"1"}}}' | awk 'tolower($1)=="mcp-session-id:"{print $2}' | tr -d '\r')
curl "${H[@]}" -H "mcp-session-id: $SID" $U -d '{"jsonrpc":"2.0","method":"notifications/initialized"}' >/dev/null
if [ "$T" = "--list" ]; then
  curl "${H[@]}" -H "mcp-session-id: $SID" $U -d '{"jsonrpc":"2.0","id":2,"method":"tools/list"}' | sed -n 's/^data: //p'
else
  curl "${H[@]}" -H "mcp-session-id: $SID" $U -d "{\"jsonrpc\":\"2.0\",\"id\":2,\"method\":\"tools/call\",\"params\":{\"name\":\"$T\",\"arguments\":$A}}" | sed -n 's/^data: //p'
fi

# Model Context Protocol

The [Model Context Protocol (MCP)](https://www.anthropic.com/news/model-context-protocol) is a standardized way for AI assistants to communicate with external tools and resources. Elroy includes built-in support for MCP, allowing other tools to read and create memories.

<div align="center">
  <p><em>MCP allows other API tools to leverage Elroy's memory capabilities:</em></p>
  <img src="../images/mcp.gif" alt="Using MCP for memory in other tools" style="max-width: 100%; margin: 20px 0;">
  <p><small>Example from <a href="https://github.com/RooVetGit/Roo-Code" target="_blank">Roo Code</a></small></p>
</div>


## Installation

To configure an [MCP](https://www.anthropic.com/news/model-context-protocol) client to use Elroy:

1. Ensure `uv` is installed
2. Use `elroy mcp print-config` to get the server's JSON configuration
3. Paste the value in the client's MCP server config


```bash
# Get Elroy's MCP server configuration
elroy mcp print-config
```

<div align="center">
  <p><em>Or, ask your tool to install the server itself:</em></p>
  <img src="../images/installing_mcp.gif" alt="Installing MCP demonstration" style="max-width: 100%; margin: 20px 0;">
</div>

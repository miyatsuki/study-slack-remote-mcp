#!/usr/bin/env python3
"""FastMCP v2 client test script"""

import asyncio
from fastmcp.client import Client

async def test_slack_mcp_server():
    """Test the Slack MCP server using FastMCP client"""
    
    # Create client with explicit server URL
    async with Client("http://localhost:8001/mcp/") as session:
        print("🔌 Connected to Slack MCP server!")
        print(f"✅ Session info: {session}")
        
        # List available tools
        print("\n📋 Available tools:")
        tools = await session.list_tools()
        for tool in tools:
            print(f"  - {tool.name}: {tool.description}")
        
        # Test get_auth_status tool
        print("\n🔍 Testing get_auth_status...")
        try:
            result = await session.call_tool("get_auth_status", {})
            print(f"  Auth status: {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # Test list_channels tool
        print("\n📂 Testing list_channels...")
        try:
            result = await session.call_tool("list_channels", {})
            print(f"  Channels: {result}")
        except Exception as e:
            print(f"  ❌ Error: {e}")
        
        # List available resources
        print("\n📚 Available resources:")
        resources = await session.list_resources()
        for resource in resources:
            print(f"  - {resource.uri}: {resource.name}")
            
        # Test session resource
        if any(r.uri == "session://info" for r in resources):
            print("\n🔍 Testing session://info resource...")
            try:
                result = await session.read_resource("session://info")
                print(f"  Session info: {result}")
            except Exception as e:
                print(f"  ❌ Error: {e}")


async def main():
    """Main entry point"""
    print("=== FastMCP v2 Client Test ===")
    print("Testing Slack MCP server at http://localhost:8001/mcp/")
    
    try:
        await test_slack_mcp_server()
    except Exception as e:
        print(f"\n❌ Connection error: {e}")
        print("Make sure the server is running on port 8001")


if __name__ == "__main__":
    asyncio.run(main())
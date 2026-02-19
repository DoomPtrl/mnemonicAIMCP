# -*- coding: utf-8 -*-
import asyncio

from dotenv import load_dotenv
from agents import Agent, Runner
from agents.mcp import MCPServerStdio
from agents.model_settings import ModelSettings


load_dotenv()


async def main() -> None:
    async with MCPServerStdio(
        name="mnemo",
        params={"command": "python", "args": ["-m", "lexicon.mnemo_mcp"]},
        cache_tools_list=True,  # speeds up repeated runs
    ) as server:
        agent = Agent(
            name="Mnemonic Agent",
            instructions="Use the MCP tools to find good initial-letter word combinations before you improvise.",
            mcp_servers=[server],
            model_settings=ModelSettings(tool_choice="required"),
        )
        prompt = "Letters=['결','근','신','상']로 기억하기 쉬운 단어 조합을 찾아줘."
        result = await Runner.run(agent, prompt)
        print(result.final_output)


if __name__ == "__main__":
    asyncio.run(main())

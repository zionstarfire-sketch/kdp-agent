import os
from agents import function_tool
from tavily import TavilyClient

@function_tool
def search_web(query: str) -> str:
    """
    Search the public internet for current information using Tavily.

    Args:
        query: The search query to investigate.

    Returns:
        Search results containing titles, URLs and snippets.
    """
    api_key = os.getenv("TAVILY_API_KEY")
    if api_key and "TAVILY_API_KEY=" in api_key:
        api_key = api_key.split("=")[-1]
    
    if not api_key:
        return "Tavily API key is not set. Cannot perform search."
        
    try:
        client = TavilyClient(api_key=api_key)
        response = client.search(query=query, max_results=10)
        results = response.get("results", [])
        
        output = []
        for result in results:
            output.append(
                f"TITLE: {result.get('title', '')}\n"
                f"URL: {result.get('url', '')}\n"
                f"SNIPPET:\n{result.get('content', '')}\n"
            )
            
        if not output:
            return "No search results found."
            
        return "\n---\n".join(output)
    except Exception as e:
        return f"Web search failed: {str(e)}"

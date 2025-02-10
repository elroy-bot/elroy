# memory_graph.py
import streamlit as st
from pyvis.network import Network
import streamlit.components.v1 as components
from pathlib import Path
import tempfile

def create_memory_graph(ctx: Elroy
    """Create an interactive memory graph visualization."""
    # Configure the network
    net = Network(
        height="600px",
        width="100%",
        bgcolor="#ffffff",
        font_color="black",
        directed=True
    )

    # Add nodes for each memory
    for memory in memories:
        # Truncate content for label, full content in hover
        label = memory['content'][:50] + "..." if len(memory['content']) > 50 else memory['content']

        net.add_node(
            memory['id'],
            label=label,
            title=memory['content'],  # Full content on hover
            shape="box",
            size=20,
            physics=False
        )

        # Add edges based on relationships (if any)
        if 'references' in memory:
            for ref in memory['references']:
                net.add_edge(memory['id'], ref, arrows='to')

    # Save to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
        net.save_graph(tmp_file.name)
        return tmp_file.name

def main():
    st.title("Memory Graph Visualization")

    # Example memories (replace with your actual memory fetching logic)
    memories = [
        {
            'id': 1,
            'content': 'Memory about document processing',
            'references': [2, 3]
        },
        {
            'id': 2,
            'content': 'Memory about source metadata',
            'references': [3]
        },
        {
            'id': 3,
            'content': 'Memory about web extraction',
            'references': []
        }
    ]

    # Create and display the graph
    graph_file = create_memory_graph(memories)

    # Read and display the HTML
    with open(graph_file, 'r', encoding='utf-8') as f:
        html = f.read()
    components.html(html, height=650)

    # Cleanup
    Path(graph_file).unlink()

if __name__ == "__main__":
    main()

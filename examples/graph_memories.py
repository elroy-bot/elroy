# memory_graph.py
from typing import List
import streamlit as st
from pyvis.network import Network
import streamlit.components.v1 as components
from pathlib import Path
import tempfile

from elroy.api import Elroy
from elroy.db.db_models import Memory
from elroy.repository.recall.transforms import MemorySource

def create_memory_graph(ai: Elroy):
    """Create an interactive memory graph visualization."""
    # Configure the network
    net = Network(
        height="600px",
        width="100%",
        bgcolor="#ffffff",
        font_color="black",
        directed=True,
    )

    node_ids = set()

    def add_node(net, memory: MemorySource):
        id = memory.id
        if not id in node_ids:
            net.add_node(
                n_id=id,
                label= memory.name,
                title= memory.to_fact(),
                shape= "box",
                size= 20,
                physics= False,
                )
            node_ids.add(id)

    node_ids = set()

    from toolz import pipe
    from toolz.curried import filter, take
    memories_to_visit: List[Memory] = pipe(
        ai.get_memories(),
        filter(lambda x: ai.get_memory_sources(x)),
        take(10),
        list,
    )


        #[x for x in ai.get_memories() if ai.get_memory_sources(x)][0:10] # Start with the root


    print(f"found {len(memories_to_visit)} memories")

    while memories_to_visit:
        memory = memories_to_visit.pop()
        if memory.id not in node_ids:
            add_node(net, memory)
            node_ids.add(memory.id)
        for source in ai.get_memory_sources(memory):
            add_node(net, source)

            if isinstance(source, Memory):
                memories_to_visit.append(source)
            net.add_edge(source.id, memory.id, arrows="to")

    # Save to a temporary file
    with tempfile.NamedTemporaryFile(delete=False, suffix='.html') as tmp_file:
        net.save_graph(tmp_file.name)
        return tmp_file.name

def main():
    st.title("Memory Graph Visualization")

    # Example memories (replace with your actual memory fetching logic)
    graph_file = create_memory_graph(Elroy())

    # Read and display the HTML
    with open(graph_file, 'r', encoding='utf-8') as f:
        html = f.read()
    components.html(html, height=650)

    # Cleanup
    Path(graph_file).unlink()

if __name__ == "__main__":
    # streamlit run graph_memories.py
    main()

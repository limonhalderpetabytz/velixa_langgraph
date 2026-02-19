# utils.py
import os

def show_graph(graph, filename="graph.png"):
    """
    Save a LangGraph structure as a PNG image when running from a .py script.
    Works with CompiledStateGraph objects.
    """
    try:
        # Generate image bytes
        png_bytes = graph.get_graph().draw_mermaid_png()

        # Save to file
        with open(filename, "wb") as f:
            f.write(png_bytes)

        abs_path = os.path.abspath(filename)
        print(f"✅ Graph visualization saved to: {abs_path}")

    except Exception as e:
        print(f"⚠️ Could not render graph visually: {e}")
        print("🧭 Fallback: Printing ASCII representation instead:\n")
        try:
            print(graph.get_graph().print_ascii())
        except Exception as ascii_err:
            print(f"(ASCII fallback failed too): {ascii_err}")





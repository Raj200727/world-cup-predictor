import time

def set_selected_match(match_id: int):
    import streamlit as st
    import streamlit.components.v1 as components

    # 1. Update the state
    st.session_state.selected_match_id = match_id

    # 2. Generate a unique ID based on the current millisecond
    # This prevents Streamlit from caching the script and ignoring rapid clicks
    unique_id = int(time.time() * 1000)

    # 3. Inject the script with the unique ID
    components.html(
        f"""
        <script id="scroll-trigger-{unique_id}">
            const target = window.parent.document.getElementById('prediction-section');
            if (target) {{
                target.scrollIntoView({{ behavior: 'smooth', block: 'start' }});
            }}
        </script>
        """,
        height=0,
        width=0,
    )
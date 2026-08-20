"""EdgeIQ Streamlit War Room shell."""


def main():
    """Launch the EdgeIQ War Room UI without coupling Streamlit to core imports."""
    import streamlit as st

    st.set_page_config(
        page_title="EdgeIQ War Room",
        layout="wide",
    )
    st.title("EdgeIQ War Room")
    st.caption("Live draft assistant shell")


if __name__ == "__main__":
    main()

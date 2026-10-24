import pandas as pd
import streamlit as st

from components.charts import knowledge_map
from components.state import get_context
from components.theme import stretch
from components.ui import page_header
from models.concepts import CONCEPTS, concept_name
from services import mastery as M

ctx = get_context()
page_header("Knowledge map", "Concepts and their prerequisites. Colour comes only from recorded attempts.", "Map")
rows = ctx.repo.mastery_rows(ctx.learner_id)
if not rows:
    st.info("No concept has been assessed yet, so every node is empty. Complete a diagnosis to start filling the map.")
st.plotly_chart(knowledge_map(rows), **stretch())
st.caption("Filled node = assessed (green ≥75%, amber 50-74%, red <50%). Purple outline = some data, below the "
           f"{M.MIN_EVIDENCE}-attempt threshold. Grey outline = no data. Arrows point from prerequisite to dependent concept.")
data = {r.concept_id: r for r in rows}
table = [{"Concept": c.name,
          "Status": M.label(data[c.id].mastery, data[c.id].attempts) if c.id in data else "No data",
          "Mastery": f"{data[c.id].mastery:.0%}" if c.id in data and M.is_assessed(data[c.id].attempts) else "—",
          "Attempts": data[c.id].attempts if c.id in data else 0,
          "Prerequisites": ", ".join(concept_name(p) for p in c.prerequisites) or "—"} for c in CONCEPTS.values()]
st.dataframe(pd.DataFrame(table), hide_index=True, **stretch())

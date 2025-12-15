import pandas as pd
import plotly.express as px
from dash import Dash, dcc, html
from dash.dependencies import Input, Output

# ---------- CONFIG ----------
INPUT_CSV = "ngram_corpus/trigrams.csv"  # <- note the .. because the app is in scatter_graph
MIN_FREQ  = 4                              # bigrams are rarer, so use a lower cutoff

# -----------------------------

# Load data
df = pd.read_csv(INPUT_CSV)
df["reviews_mentioning_ngram"] = df["reviews_mentioning_ngram"].astype(int)
df["avg_rating_0_5"] = df["avg_rating_0_5"].astype(float)

# Keep only reasonably frequent words
df = df[df["reviews_mentioning_ngram"] >= MIN_FREQ]

# Build base scatter figure
fig = px.scatter(
    df,
    x="reviews_mentioning_ngram",
    y="avg_rating_0_5",
    color="avg_rating_0_5",
    color_continuous_scale="RdYlGn",
    range_color=(0, 5),  # <-- force color scale from 0 to 5
    log_x=True,
    custom_data=["ngram", "reviews_mentioning_ngram", "avg_rating_0_5"],
    labels={
        "reviews_mentioning_ngram": "Reviews mentioning word",
        "avg_rating_0_5": "Average rating (0–5)",
    },
    title="Word frequency vs rating (interactive)",
)


fig.update_traces(
    mode="markers",
    marker=dict(
        size=10,
        opacity=0.7,
        line=dict(width=0),
    ),
    hovertemplate=(
        "<b>%{customdata[0]}</b><br>"  # word
        "Reviews: %{customdata[1]}<br>"
        "Avg rating: %{customdata[2]:.2f}/5"
        "<extra></extra>"
    ),
)

fig.update_layout(
    title="Word frequency vs rating",
    xaxis_title="Reviews mentioning word",
    yaxis_title="Average rating (0–5)",
    yaxis=dict(range=[0, 5]),
    clickmode="event+select",  # enables click events
)

# -------- Dash app --------
app = Dash(__name__)

app.layout = html.Div(
    style={"maxWidth": "1200px", "margin": "0 auto", "fontFamily": "sans-serif"},
    children=[
        html.H2("Word frequency vs rating (interactive)"),
        dcc.Graph(
            id="word-scatter",
            figure=fig,
            style={"height": "80vh"},
        ),
        html.Div(
            id="clicked-info",
            style={"marginTop": "20px", "fontSize": "18px"},
            children="Click on a circle to see the word and its stats.",
        ),
    ],
)

@app.callback(
    Output("clicked-info", "children"),
    Input("word-scatter", "clickData"),
)
def display_click_data(clickData):
    """Update the text below the chart when a point is clicked."""
    if clickData is None:
        return "Click on a circle to see the word and its stats."

    point = clickData["points"][0]
    word   = point["customdata"][0]
    freq   = point["customdata"][1]
    rating = point["customdata"][2]

    return (
        f"Selected word: '{word}' — "
        f"reviews mentioning it: {freq}, "
        f"average rating: {rating:.2f}/5"
    )


if __name__ == "__main__":
    app.run(debug=True)


# Review-Plotter-Generator

A simple scatter-graph generator that builds a visual graph from review data.  
Right now it is wired to work with IIT review data, but it can be adapted to work with reviews from other sources.

> Status: early alpha (`Alpha 0.1`)

---

## Features

- Generates a scatter plot from review-related data.
- Built as a small web app using [Dash](https://dash.plotly.com/).
- Currently focused on IIT review data, with the intent to generalize to other review sets later.

---

## Tech stack

- **Language:** Python 3
- **Framework:** Dash (for the web UI and interactive scatter plot)

---

## Project structure (known parts)

```text
.
├── scatter_graph/
│   └── word_scatter_app.py    # Main Dash app that renders the scatter plot
└── README.md

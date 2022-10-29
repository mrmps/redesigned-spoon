#!/usr/bin/env python

import streamlit as st
from streamlit_plotly_events import plotly_events
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px
from main import *
import copy

st.title('Arvix Semantic Paper Searcher')
col1, col2 = st.columns(spec=[3, 2])

with col1:
    query = st.text_input('Please input your query here: ', 'Celestial bodies and physics')
with col2:
    num_nearest = int(st.number_input('Please input the number of papers to find: ', value=100))

co = getCohereClient(get_key())

with st.sidebar:
    st.header('Summary')
    subject_placeholder = st.empty()
    st.header('Title')
    title_placeholder = st.empty()
    st.header('Summary')
    description_placeholder = st.empty()
    st.header('Link')
    link_placeholder = st.empty()


# Get dataframe
df = getDataFrame('data_100_with_link.csv')

# Get vectors using coheres embeddings
embeddings = getEmbeddings(co, df)

# Save embeddings as Annoy
indexfile = 'index.ann'
saveBuild(embeddings, indexfile)

# Get query embeddings and append to embeddings
query_embed = get_query_embed(co, query)

# Get nearest points
nearest_ids = get_query_nn(indexfile, query_embed, num_nearest)
df = df.loc[nearest_ids[0]].reset_index()
nn_embeddings = embeddings[nearest_ids[0]]

df.loc[num_nearest] = [-1, 'Query', query, '', '']
all_embeddings = np.vstack([nn_embeddings, query_embed])

# Cluster them using dendrograms & Plot them
model = fitModel(nn_embeddings)

#linkages = plotDendrogram(model)

# Map the nearest embeddings to 2d
umap_embeds = getUMAPEmbeddings(all_embeddings)

# level 0 = show each doc as own cluster, level n = 1 cluster
def get_clusters(level):
    cluster_combine_order = copy.deepcopy(model.children_)

    cluster_mappings = dict()
    for cluster in model.labels_:
        cluster_mappings[cluster] = [cluster]

    n = len(cluster_mappings)
    for i in range(level):
        values = cluster_combine_order[0]
        cluster_combine_order = np.delete(cluster_combine_order, 0, axis=0)
        cluster_mappings[n] = cluster_mappings[values[0]] + cluster_mappings[values[1]]
        cluster_mappings.pop(values[0])
        cluster_mappings.pop(values[1])
        n += 1

    clusters = []
    for v in cluster_mappings.values():
        (x0, y0), (x1, y1) = umap_embeds[v[0]], umap_embeds[v[0]]
        for i in v:
            x0 = min(umap_embeds[i][0], x0)
            y0 = min(umap_embeds[i][1], y0)
            x1 = max(umap_embeds[i][0], x1)
            y1 = max(umap_embeds[i][1], y1)
        clusters.append(tuple([x0, y0, x1, y1]))
    return clusters

placeholder=st.empty()
level = st.slider('Hierarchical cluster slider', min_value=0, max_value=num_nearest, step=1, value=num_nearest)

clusters = get_clusters(level-1)

with placeholder.container():
    # Plot points on 2d chart
    fig = plot2DChart(df, umap_embeds, clusters)
    selected_point = plotly_events(fig)
    if len(selected_point) > 0:
        data = getData(selected_point[0]['x'], selected_point[0]['y'], umap_embeds, df)
        subject_placeholder.write(data['Subject'])
        title_placeholder.write(data['Title'])
        description_placeholder.write(data['Summary'])
        link_placeholder.write(data['Link'])

#!/usr/bin/env python

import streamlit as st
from streamlit_plotly_events import plotly_events
import pandas as pd
import numpy as np
import matplotlib.pyplot as plt
import plotly.express as px

from main import *
import copy

# Get dataframe
df = getDataFrame('data_100_with_link.csv')

st.title('Arvix Semantic Paper Searcher')
col1, col2 = st.columns(spec=[3, 2])

with col1:
    query = st.text_input('Please input your query here: ', 'Celestial bodies and physics')
with col2:
    num_nearest = int(st.number_input('Please input the number of papers to find: ', value=100, min_value=1, max_value=len(df)))

co = getCohereClient(get_key())

def clear_selected_index():
    st.session_state['selected_index'] = None
    st.session_state['clear_sidebar'] = True

if 'first' not in st.session_state:
    st.session_state.first = True

with st.sidebar:
    st.header('Summary')
    subject_placeholder = st.empty()
    st.header('Title')
    title_placeholder = st.empty()
    st.header('Summary')
    description_placeholder = st.empty()
    st.header('Link')
    link_placeholder = st.empty()
    st.button('Clear Selected Point', on_click=clear_selected_index)

    if st.session_state.get('clear_sidebar', False):
        subject_placeholder.write('')
        title_placeholder.write('')
        description_placeholder.write('')
        link_placeholder.write('')
        st.session_state['clear_sidebar'] = False


selected_index = st.empty()

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

# Get the word frequencies
word_frequencies = getWordFrequencies()

# level 0 = show each doc as own cluster, level n = 1 cluster
@st.cache
def get_clusters(level):
    word_frequencies_combined = copy.deepcopy(word_frequencies)
    cluster_combine_order = copy.deepcopy(model.children_)

    cluster_mappings = dict()
    for cluster in model.labels_:
        cluster_mappings[cluster] = [cluster]

    n = len(cluster_mappings)
    for i in range(level):
        indicies_of_merged_clusters = cluster_combine_order[0]
        cluster_combine_order = np.delete(cluster_combine_order, 0, axis=0)
        cluster_mappings[n] = cluster_mappings.pop(indicies_of_merged_clusters[0]) \
                              + cluster_mappings.pop(indicies_of_merged_clusters[1])

        word_frequencies_combined[n] = word_frequencies_combined.pop(indicies_of_merged_clusters[0]) \
                                       + word_frequencies_combined.pop(indicies_of_merged_clusters[1])

        n += 1

    def convex_hull(points):
        """Computes the convex hull of a set of 2D points.

        Input: an iterable sequence of (x, y) pairs representing the points.
        Output: a list of vertices of the convex hull in counter-clockwise order,
          starting from the vertex with the lexicographically smallest coordinates.
        Implements Andrew's monotone chain algorithm. O(n log n) complexity.
        """

        # Sort the points lexicographically (tuples are compared lexicographically).
        # Remove duplicates to detect the case we have just one unique point.
        points = sorted(set(points))

        # Boring case: no points or a single point, possibly repeated multiple times.
        if len(points) <= 1:
            return points

        # 2D cross product of OA and OB vectors, i.e. z-component of their 3D cross product.
        # Returns a positive value, if OAB makes a counter-clockwise turn,
        # negative for clockwise turn, and zero if the points are collinear.
        def cross(o, a, b):
            return (a[0] - o[0]) * (b[1] - o[1]) - (a[1] - o[1]) * (b[0] - o[0])

        # Build lower hull
        lower = []
        for p in points:
            while len(lower) >= 2 and cross(lower[-2], lower[-1], p) <= 0:
                lower.pop()
            lower.append(p)

        # Build upper hull
        upper = []
        for p in reversed(points):
            while len(upper) >= 2 and cross(upper[-2], upper[-1], p) <= 0:
                upper.pop()
            upper.append(p)

        # Concatenation of the lower and upper hulls gives the convex hull.
        # Last point of each list is omitted because it is repeated at the beginning of the other list.
        return lower[:-1] + upper[:-1]

    # Calculate boundaries
    for k in cluster_mappings.keys():
        cluster_mappings[k] = map(lambda i: (umap_embeds[i][0], umap_embeds[i][1]),cluster_mappings[k])
        cluster_mappings[k] = convex_hull(cluster_mappings[k])
        x_list, y_list = [], []
        for x, y in cluster_mappings[k]:
            x_list.append(x)
            y_list.append(y)
        if len(x_list) == 2:
            # inv_slope = (x_list[1]-x_list[0])/(y_list[1]-y_list[0])
            dx = (y_list[1] - y_list[0]) * 0.1
            dy = (x_list[1] - x_list[0]) * 0.1
            x_list[0] += dx
            y_list[0] += dy

            x_list[1] += dx
            y_list[1] += dy

            x_list.append(x_list[1]-2*dx)
            y_list.append(y_list[1]-2*dy)

        x_list.append(x_list[0])
        y_list.append(y_list[0])

        cluster_mappings[k] = (x_list, y_list, word_frequencies_combined[k])

    return cluster_mappings

placeholder=st.empty()

if st.session_state.get('selected_index', None) is not None:
    # this means we have selected a value and the levels should only be the number of merges for the
    # cluster that the selected item is in (TODO: changes the max_value)
    level = st.slider('Hierarchical cluster slider', min_value=0, max_value=num_nearest, step=1, value=num_nearest)
else:
    level = st.slider('Hierarchical cluster slider', min_value=0, max_value=num_nearest, step=1, value=num_nearest)

clusters = get_clusters(level - 1)

with placeholder.container():
    # Plot points on 2d chart
    fig = plot2DChart(df, umap_embeds, clusters)
    selected_point = plotly_events(fig)
    if len(selected_point) > 0 and (st.session_state.get('selected_index', None) is not None
                                    or st.session_state.first or st.session_state.get('old_selected_point', None) != selected_point
                                    ):
        selected_x = selected_point[0]['x']
        selected_y = selected_point[0]['y']
        data = getData(selected_x, selected_y, umap_embeds, df)
        st.session_state['selected_index'] = data['index']
        subject_placeholder.write(data['Subject'])
        title_placeholder.write(data['Title'])
        description_placeholder.write(data['Summary'])
        link_placeholder.write(data['Link'])
        st.session_state.first = False
        st.session_state.old_selected_point = selected_point

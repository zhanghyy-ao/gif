# -*- coding: utf-8 -*-
"""
kg_schema.py - Pydantic schemas for knowledge graph
"""
from pydantic import BaseModel
from typing import List, Optional, Literal

NodeType = Literal["Concept","Method","Dataset","Metric","Result","Task","Component"]

class Node(BaseModel):
    id: str
    type: NodeType
    name: str
    summary: Optional[str] = None

class Edge(BaseModel):
    source: str
    target: str
    relation: str  # e.g., "improves", "uses", "evaluated_on", "compared_to"

class Graph(BaseModel):
    nodes: List[Node]
    edges: List[Edge]

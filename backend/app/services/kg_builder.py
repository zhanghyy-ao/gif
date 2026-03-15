# -*- coding: utf-8 -*-
"""
kg_builder.py - Build a lightweight knowledge graph from parsed paper_struct
- Rule-based extraction of key concepts/methods/datasets/metrics/results
- Optional: summarization via DashScope (if needed later)
"""
from __future__ import annotations
from typing import Dict, Any, List
import re
import uuid
from .kg_schema import Node, Edge, Graph


def _new_id(prefix: str) -> str:
    return f"{prefix}_{uuid.uuid4().hex[:8]}"


def extract_concepts(text: str) -> List[str]:
    # naive: capitalized terms with 2+ words or CamelCase
    terms = set()
    for m in re.finditer(r"\b([A-Z][a-zA-Z]+(?:\s+[A-Z][a-zA-Z]+)+|[A-Z][a-z]+[A-Z][a-zA-Z]+)\b", text):
        t = m.group(1)
        if len(t.split()) <= 6:
            terms.add(t)
    return list(sorted(terms))[:20]


def extract_methods(text: str) -> List[str]:
    patterns = [r"we (?:propose|introduce|present) ([^\.;:]{5,80})", r"our method ([^\.;:]{5,80})"]
    found = []
    low = text.lower()
    for pat in patterns:
        for m in re.finditer(pat, low):
            span = text[m.start():m.end()]
            found.append(span.strip())
    return found[:10]


def extract_datasets(text: str) -> List[str]:
    names = re.findall(r"\b(MNIST|CIFAR-10|CIFAR-100|ImageNet|COCO|LVIS|KITTI|Cityscapes|SQuAD|GLUE|SuperGLUE)\b", text)
    return list(sorted(set(names)))


def extract_metrics(text: str) -> List[str]:
    names = re.findall(r"\b(accuracy|mAP|BLEU|ROUGE|F1|IoU|PSNR|SSIM|AUC)\b", text, flags=re.I)
    return list(sorted(set([n.upper() for n in names])))


def extract_results(text: str) -> List[str]:
    # naive capture of "improve by X%" style sentences
    res = []
    for m in re.finditer(r"(improv\w+|outperform\w+|state-of-the-art)[^\.!?]{0,100}(\d+\.?\d*\s*%|points|pts)", text, flags=re.I):
        res.append(text[m.start():m.end()])
    return res[:10]


def build_graph(paper_struct: Dict[str, Any]) -> Graph:
    text = "\n".join([paper_struct.get("abstract", "")] + [s.get("content", "") for s in paper_struct.get("sections", [])])
    nodes: List[Node] = []
    edges: List[Edge] = []

    # Concepts
    for c in extract_concepts(text):
        nodes.append(Node(id=_new_id("C"), type="Concept", name=c))

    # Method (compact node)
    for m in extract_methods(text):
        nid = _new_id("M")
        nodes.append(Node(id=nid, type="Method", name=m))
        # link method to concepts (first 3)
        for c in nodes:
            if c.type == "Concept":
                edges.append(Edge(source=nid, target=c.id, relation="describes"))
                if len([e for e in edges if e.source == nid]) >= 3:
                    break

    # Datasets
    for d in extract_datasets(text):
        nodes.append(Node(id=_new_id("D"), type="Dataset", name=d))

    # Metrics
    for m in extract_metrics(text):
        nodes.append(Node(id=_new_id("T"), type="Metric", name=m))

    # Results
    for r in extract_results(text):
        nodes.append(Node(id=_new_id("R"), type="Result", name=r))

    return Graph(nodes=nodes, edges=edges)

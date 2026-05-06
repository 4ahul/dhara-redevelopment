"""
Semantic Text Splitter
Splits documents on natural boundaries (paragraphs, headings, lists) instead of fixed sizes.
Maintains context and preserves logical sections.
"""

import re
from dataclasses import dataclass
from typing import Any


@dataclass
class Chunk:
    """A semantic chunk with metadata"""

    content: str
    source: str
    chunk_type: str  # paragraph, heading, list, table, clause
    topic: str
    section: str
    page: int | None = None
    chunk_index: int = 0


class SemanticChunker:
    """
    Semantic chunker that splits text on natural boundaries.
    Keeps related content together for better retrieval.
    """

    # Patterns for different content types
    HEADING_PATTERNS = [
        r"^#{1,6}\s+.+$",  # Markdown headings
        r"^[0-9]+\.\s+.+$",  # Numbered headings (1. , 2. )
        r"^[A-Z][A-Z\s]+$",  # ALL CAPS headings
        r"^[A-Z][a-z]+(\s+[A-Z][a-z]+)*:$",  # Title Case headings:
        r"^Regulation\s+[0-9]+",  # Regulation headings
        r"^Rule\s+[0-9]+",  # Rule headings
        r"^CHAPTER\s+[IVX]+",  # Chapter headings
        r"^PART\s+[IVX]+",  # Part headings
        # Devanagari/Marathi/Hindi headings
        r"^अध्याय\s+[०-९\d]+",  # अध्याय 1 (Chapter)
        r"^खंड\s+[०-९\dIVX]+",  # खंड (Part)
        r"^नियम\s+[०-९\d]+",  # नियम (Rule)
        r"^धारा\s+[०-९\d]+",  # धारा (Section/Clause)
        r"^कलम\s+[०-९\d]+",  # कलम (Article)
        r"^परिशिष्ट\s+[०-९\d]+",  # परिशिष्ट (Appendix)
        r"^तालिका\s+[०-९\d]+",  # तालिका (Table)
        r"^[\u0900-\u097f][\u0900-\u097f\s]{5,}$",  # All Devanagari CAPS-like
    ]

    LIST_PATTERNS = [
        r"^[\-\*\•]\s+.+$",  # Bullet points
        r"^\d+[\.\)]\s+.+$",  # Numbered list items
        r"^[(a-zA-Z)]\)\s+.+$",  # Lettered list items
        r"^[०-९]+[\.\)]\s+.+$",  # Devanagari numbered items
        r"^\([०-९\d]+\)\s+.+$",  # (१), (२) Devanagari numbered parens
    ]

    TABLE_PATTERNS = [
        r"\|.+\|.+\|",  # Markdown tables
        r"^\s*\d+\s+\d+\s+\d+",  # Tabular data
        r"^\s*[०-९]+\s+[०-९]+",  # Devanagari tabular data
    ]

    CLAUSE_PATTERNS = [
        r"^\([0-9]+\)",  # (1), (2)
        r"^\([a-z]+\)",  # (a), (b)
        r"^[0-9]+[a-z]?\.\s+",  # 1. , 1a.
        r"^\([०-९]+\)",  # (१), (२) Devanagari
        r"^उपधारा\s+[०-९\d]+",  # उपधारा (Sub-section)
        r"^उपकलम\s+[०-९\d]+",  # उपकलम (Sub-clause)
    ]

    def __init__(
        self,
        min_chunk_size: int = 100,
        max_chunk_size: int = 1500,
        overlap: int = 100,
        headings_only: bool = False,
    ):
        self.min_chunk_size = min_chunk_size
        self.max_chunk_size = max_chunk_size
        self.overlap = overlap
        self.headings_only = headings_only

        # Compile patterns
        self.heading_re = re.compile("|".join(self.HEADING_PATTERNS), re.MULTILINE)
        self.list_re = re.compile("|".join(self.LIST_PATTERNS), re.MULTILINE)
        self.table_re = re.compile("|".join(self.TABLE_PATTERNS), re.MULTILINE)
        self.clause_re = re.compile("|".join(self.CLAUSE_PATTERNS), re.MULTILINE)

    def identify_content_type(self, line: str) -> str:
        """Identify the type of content line"""
        if self.heading_re.match(line.strip()):
            return "heading"
        if self.clause_re.match(line.strip()):
            return "clause"
        if self.list_re.match(line.strip()):
            return "list"
        if self.table_re.match(line.strip()):
            return "table"
        return "paragraph"

    def split_into_sections(self, text: str) -> list[str]:
        """Split text into logical sections based on headings"""
        lines = text.split("\n")
        sections = []
        current_section = []

        for line in lines:
            line_stripped = line.strip()
            content_type = self.identify_content_type(line_stripped)

            if content_type == "heading":
                # Save previous section
                if current_section:
                    sections.append("\n".join(current_section))
                current_section = [line]
            else:
                current_section.append(line)

        # Add last section
        if current_section:
            sections.append("\n".join(current_section))

        return sections

    def split_section(self, section: str, section_name: str = "") -> list[Chunk]:
        """Split a section into chunks while preserving context"""
        chunks = []

        # Split by paragraphs first
        paragraphs = re.split(r"\n\n+", section)

        current_chunk = []
        current_size = 0
        chunk_index = 0

        for para in paragraphs:
            stripped_para = para.strip()
            if not stripped_para:
                continue

            para_type = self.identify_content_type(stripped_para)

            # Handle headings - start new chunk
            if para_type == "heading":
                if current_chunk and sum(len(c) for c in current_chunk) >= self.min_chunk_size:
                    chunks.append(self._create_chunk(current_chunk, section_name, chunk_index))
                    chunk_index += 1
                current_chunk = [para]
                current_size = len(para)
                continue

            # Check if adding this paragraph would exceed max size
            if current_size + len(para) > self.max_chunk_size and current_chunk:
                chunks.append(self._create_chunk(current_chunk, section_name, chunk_index))
                chunk_index += 1

                # Handle overlap for context
                if self.overlap > 0 and len(current_chunk) > 1:
                    overlap_text = "\n\n".join(current_chunk[-2:])
                    if len(overlap_text) <= self.overlap:
                        current_chunk = [overlap_text, para]
                        current_size = len(overlap_text) + len(para)
                    else:
                        current_chunk = [para]
                        current_size = len(para)
                else:
                    current_chunk = [para]
                    current_size = len(para)
            else:
                current_chunk.append(para)
                current_size += len(para) + 2  # +2 for newline

        # Add final chunk
        if current_chunk and sum(len(c) for c in current_chunk) >= self.min_chunk_size:
            chunks.append(self._create_chunk(current_chunk, section_name, chunk_index))

        return chunks

    def _create_chunk(self, lines: list[str], section: str, index: int) -> Chunk:
        """Create a Chunk object from lines, preserving section context"""
        content = "\n\n".join(lines)
        first_line = lines[0].strip() if lines else ""

        # Prepend section name if it's not already in the first line
        if section and section not in first_line:
            content = f"[{section}] {content}"

        # Determine chunk type from first line
        chunk_type = self.identify_content_type(first_line)
        if chunk_type == "paragraph":
            chunk_type = "text"

        # Extract topic from heading if available
        topic = section
        if self.heading_re.match(first_line):
            topic = first_line.lstrip("#").strip()

        return Chunk(
            content=content,
            source="",
            chunk_type=chunk_type,
            topic=topic,
            section=section,
            chunk_index=index,
        )

    def chunk_text(self, text: str, source: str = "") -> list[tuple[str, str]]:
        """
        Main method to chunk text.
        Returns list of (chunk_text, metadata_json) tuples.
        """
        # First split into sections
        sections = self.split_into_sections(text)

        all_chunks = []

        for section in sections:
            # Get section heading
            section_name = ""
            first_line = section.split("\n")[0].strip()
            if self.identify_content_type(first_line) == "heading":
                section_name = first_line.lstrip("#").strip()

            # Split section into chunks
            section_chunks = self.split_section(section, section_name)
            all_chunks.extend(section_chunks)

        # Add source to each chunk
        result = []
        for chunk in all_chunks:
            chunk.source = source
            metadata = f"{chunk.chunk_type}|{chunk.topic}|{chunk.section}"
            result.append((chunk.content, metadata))

        return result


class HybridChunker:
    """
    Hybrid approach: combines semantic chunking with fixed-size for flexibility.
    Uses semantic split when possible, falls back to fixed-size for edge cases.
    """

    def __init__(
        self,
        semantic_max: int = 1500,
        fallback_size: int = 800,
        overlap: int = 100,
    ):
        self.semantic_chunker = SemanticChunker(
            max_chunk_size=semantic_max,
            min_chunk_size=100,
            overlap=overlap,
        )
        self.fallback_size = fallback_size
        self.overlap = overlap

    def chunk_text(self, text: str, source: str = "") -> list[tuple[str, str]]:
        """Chunk text using hybrid approach"""
        # Try semantic chunking first
        chunks = self.semantic_chunker.chunk_text(text, source)

        # Check if any chunks are too small, apply fallback
        result = []
        for chunk_text, metadata in chunks:
            if len(chunk_text) < 50:
                # Too small, try to merge with previous
                if result:
                    prev_text, prev_meta = result[-1]
                    if len(prev_text) + len(chunk_text) < self.fallback_size + 200:
                        result[-1] = (prev_text + "\n\n" + chunk_text, prev_meta)
                        continue
                result.append((chunk_text, metadata))
            else:
                result.append((chunk_text, metadata))

        return result


def create_chunker(chunking_strategy: str = "semantic", **kwargs) -> Any:
    """Factory function to create appropriate chunker"""
    if chunking_strategy == "semantic":
        return SemanticChunker(**kwargs)
    if chunking_strategy == "hybrid":
        return HybridChunker(**kwargs)
    # Default to langchain's RecursiveCharacterTextSplitter
    from langchain_text_splitters import RecursiveCharacterTextSplitter

    return RecursiveCharacterTextSplitter(**kwargs)


if __name__ == "__main__":
    # Test the chunker
    test_text = """
# Chapter 1: Introduction to FSI

## What is FSI?

Floor Space Index (FSI) is the ratio of the total floor area of a building to the total area of the plot on which the building is constructed.

FSI is calculated by dividing the total built-up area by the total plot area.

## FSI Regulations in Pune

In Pune, FSI is governed by UDCPR (Unified Development Control and Promotion Regulations). The base FSI for residential buildings is as follows:

1. For plots up to 2000 sq.m - FSI up to 3.0
2. For plots above 2000 sq.m - FSI up to 2.5
3. For plots in congested areas - FSI up to 4.0

### Road Width Requirements

The maximum permissible FSI also depends on the road width:

| Road Width | Maximum FSI |
|-----------|-------------|
| 9m to 12m | 2.00 |
| 12m to 18m | 2.50 |
| 18m to 24m | 3.00 |

(1) For plots with road width less than 9m, the FSI shall be reduced by 20%.

(2) Premium FSI may be purchased at 35% of Ready Reckoner Rate.

## Conclusion

FSI regulations are crucial for property development and must be carefully considered before planning any construction activity.
    """

    chunker = SemanticChunker(max_chunk_size=600)
    chunks = chunker.chunk_text(test_text, "test.txt")

    for _i, (_text, _meta) in enumerate(chunks):
        pass

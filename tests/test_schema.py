from sentcite.schema import (
    Citation,
    CitedAnswer,
    CitedSentence,
    Chunk,
    Sentence,
)


def test_sentence_roundtrip():
    s = Sentence(
        sentence_id="doc1::p001::c00::s00",
        chunk_id="doc1::p001::c00",
        document_id="doc1",
        text="Ordinary and necessary expenses are deductible.",
        page=1,
        section_path=["§ 162", "(a)"],
        char_start=0,
        char_end=47,
    )
    assert s.char_end > s.char_start
    assert s.page == 1


def test_cited_answer_builds():
    sent = Sentence(
        sentence_id="doc1::p001::c00::s00",
        chunk_id="doc1::p001::c00",
        document_id="doc1",
        text="x",
        page=1,
        char_start=0,
        char_end=1,
    )
    chunk = Chunk(
        chunk_id="doc1::p001::c00",
        document_id="doc1",
        page=1,
        text="x",
        token_count=1,
        sentences=[sent],
    )
    ca = CitedAnswer(
        question="q?",
        answer_text="a.",
        sentences=[
            CitedSentence(
                index=0,
                text="a.",
                citations=[
                    Citation(
                        sentence_id=sent.sentence_id,
                        chunk_id=chunk.chunk_id,
                        document_id=chunk.document_id,
                        page=chunk.page,
                        confidence=0.9,
                        source="aligner",
                    )
                ],
            )
        ],
        strategy="post_gen_alignment",
        model="gpt-4o",
        retrieved_chunk_ids=[chunk.chunk_id],
    )
    assert ca.sentences[0].citations[0].confidence == 0.9

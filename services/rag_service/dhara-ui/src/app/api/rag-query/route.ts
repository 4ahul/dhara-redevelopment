import { NextRequest, NextResponse } from "next/server";
import { spawn } from "child_process";
import { promisify } from "util";

const exec = promisify(require("child_process").exec);

export async function POST(request: NextRequest) {
    try {
        const { query } = await request.json();

        if (!query || typeof query !== "string") {
            return NextResponse.json(
                { error: "Query is required" },
                { status: 400 }
            );
        }

        const pythonScript = `
import sys
import os
from pathlib import Path
root_dir = Path(os.getcwd())
sys.path.insert(0, str(root_dir))
from intelligent_rag import IntelligentRAG
import json

rag = IntelligentRAG()
result = rag.query('${query.replace(/'/g, "\\'")}')
print(json.dumps(result))
`;

        const { stdout, stderr } = await exec(
            `python3 -c "${pythonScript.replace(/"/g, '\\"')}"`,
            { timeout: 60000 }
        );

        if (stderr) {
            console.error("Python error:", stderr);
        }

        const result = JSON.parse(stdout);

        return NextResponse.json({
            answer: result.answer,
            sources: result.get("sources", []),
            clauses: result.get("clauses", []),
            confidence: result.get("confidence", 0),
            suggested_queries: result.get("suggestions", [])
        });
    } catch (error) {
        console.error("RAG query error:", error);
        return NextResponse.json(
            { error: "Failed to process query" },
            { status: 500 }
        );
    }
}

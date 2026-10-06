from pathlib import Path
import os
import uuid

from flask import (
    Flask,
    request,
    jsonify,
    render_template
)
from werkzeug.utils import secure_filename

from src.pipeline import RAGPipeline


# ==================================================
# FLASK CONFIGURATION
# ==================================================

app = Flask(__name__)

BASE_DIR = Path(__file__).resolve().parent

UPLOAD_FOLDER = BASE_DIR / "uploads"

UPLOAD_FOLDER.mkdir(
    parents=True,
    exist_ok=True
)

app.config["UPLOAD_FOLDER"] = str(
    UPLOAD_FOLDER
)

# 50 MB maximum request size
app.config["MAX_CONTENT_LENGTH"] = (
    50 * 1024 * 1024
)


# ==================================================
# GLOBAL RAG PIPELINE
# ==================================================

rag_pipeline = RAGPipeline()


# ==================================================
# HOME
# ==================================================

@app.route("/")
def index():

    return render_template(
        "index.html"
    )


# ==================================================
# UPLOAD PDF DOCUMENTS
# ==================================================

@app.route(
    "/upload",
    methods=["POST"]
)
def upload():

    try:

        # --------------------------------------------------
        # Check files
        # --------------------------------------------------

        files = request.files.getlist(
            "files"
        )

        if not files:

            return jsonify({

                "success":
                    False,

                "error":
                    "No PDF files were uploaded."

            }), 400


        # --------------------------------------------------
        # Remove empty file selections
        # --------------------------------------------------

        valid_files = [

            file

            for file in files

            if file
            and file.filename
            and file.filename.strip()

        ]


        if not valid_files:

            return jsonify({

                "success":
                    False,

                "error":
                    "No valid files were uploaded."

            }), 400


        # --------------------------------------------------
        # Validate extensions
        # --------------------------------------------------

        invalid_files = [

            file.filename

            for file in valid_files

            if Path(
                file.filename
            ).suffix.lower() != ".pdf"

        ]


        if invalid_files:

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "Only PDF files are supported. "
                        f"Invalid files: "
                        f"{', '.join(invalid_files)}"
                    )

            }), 400


        # --------------------------------------------------
        # Create a unique upload directory
        # --------------------------------------------------

        upload_id = uuid.uuid4().hex

        session_folder = (
            UPLOAD_FOLDER / upload_id
        )

        session_folder.mkdir(
            parents=True,
            exist_ok=True
        )


        saved_paths = []

        saved_filenames = []


        # --------------------------------------------------
        # Save every uploaded PDF
        # --------------------------------------------------

        for file in valid_files:

            original_name = file.filename

            filename = secure_filename(
                original_name
            )


            if not filename:

                return jsonify({

                    "success":
                        False,

                    "error":
                        (
                            "Invalid filename: "
                            f"{original_name}"
                        )

                }), 400


            save_path = (
                session_folder / filename
            )


            # --------------------------------------------------
            # Avoid filename collisions
            # --------------------------------------------------

            if save_path.exists():

                stem = save_path.stem

                suffix = save_path.suffix

                filename = (
                    f"{stem}_{uuid.uuid4().hex[:8]}"
                    f"{suffix}"
                )

                save_path = (
                    session_folder / filename
                )


            file.save(
                str(save_path)
            )


            saved_paths.append(
                str(save_path)
            )

            saved_filenames.append(
                filename
            )


        # --------------------------------------------------
        # Ingest ALL documents together
        # --------------------------------------------------

        print(
            "\n" + "=" * 60
        )

        print(
            "FLASK UPLOAD"
        )

        print(
            "=" * 60
        )

        print(
            "Documents received:",
            len(saved_paths)
        )


        for filename in saved_filenames:

            print(
                " -",
                filename
            )


        stats = rag_pipeline.ingest(
            saved_paths
        )


        # --------------------------------------------------
        # Return ingestion information
        # --------------------------------------------------

        return jsonify({

            "success":
                True,

            "message":
                "Documents uploaded and processed successfully.",

            "upload_id":
                upload_id,

            "documents":
                stats.get(
                    "documents",
                    len(saved_paths)
                ),

            "filenames":
                stats.get(
                    "filenames",
                    saved_filenames
                ),

            "pages":
                stats.get(
                    "pages",
                    0
                ),

            "chunks":
                stats.get(
                    "chunks",
                    0
                ),

            "text_retrieval":
                stats.get(
                    "text_retrieval",
                    False
                ),

            "multimodal":
                stats.get(
                    "multimodal",
                    True
                )

        }), 200


    except Exception as e:

        print(
            "\nUPLOAD ERROR:"
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ==================================================
# ASK QUESTION
# ==================================================

@app.route(
    "/ask",
    methods=["POST"]
)
def ask():

    try:

        # --------------------------------------------------
        # Check pipeline
        # --------------------------------------------------

        if not rag_pipeline.is_ready():

            return jsonify({

                "success":
                    False,

                "error":
                    (
                        "Please upload at least "
                        "one PDF before asking "
                        "a question."
                    )

            }), 400


        # --------------------------------------------------
        # Read JSON body
        # --------------------------------------------------

        data = request.get_json(
            silent=True
        )


        if not data:

            return jsonify({

                "success":
                    False,

                "error":
                    "Invalid request body."

            }), 400


        question = data.get(
            "question",
            ""
        )


        # --------------------------------------------------
        # Validate question
        # --------------------------------------------------

        if not isinstance(
            question,
            str
        ):

            return jsonify({

                "success":
                    False,

                "error":
                    "Question must be text."

            }), 400


        question = question.strip()


        if not question:

            return jsonify({

                "success":
                    False,

                "error":
                    "Please enter a question."

            }), 400


        # --------------------------------------------------
        # Optional top-k
        # --------------------------------------------------

        k = data.get(
            "k",
            5
        )


        try:

            k = int(k)

        except (
            TypeError,
            ValueError
        ):

            k = 5


        k = max(
            1,
            min(k, 10)
        )


        print(
            "\n" + "=" * 60
        )

        print(
            "QUESTION RECEIVED"
        )

        print(
            "=" * 60
        )

        print(
            "Question:",
            question
        )

        print(
            "Top-k:",
            k
        )


        # --------------------------------------------------
        # Ask RAG pipeline
        # --------------------------------------------------

        result = rag_pipeline.ask(

            question,

            k=k

        )


        # --------------------------------------------------
        # Return answer
        # --------------------------------------------------

        return jsonify({

            "success":
                True,

            "answer":
                result.get(
                    "answer",
                    ""
                ),

            "sources":
                result.get(
                    "sources",
                    []
                ),

            "multimodal":
                result.get(
                    "multimodal",
                    True
                )

        }), 200


    except Exception as e:

        print(
            "\nASK ERROR:"
        )

        print(
            type(e).__name__
        )

        print(
            str(e)
        )


        return jsonify({

            "success":
                False,

            "error":
                str(e)

        }), 500


# ==================================================
# HEALTH CHECK
# ==================================================

@app.route(
    "/health",
    methods=["GET"]
)
def health():

    return jsonify({

        "status":
            "ok",

        "ready":
            rag_pipeline.is_ready(),

        "documents":
            len(
                rag_pipeline.documents
            ),

        "pages":
            len(
                rag_pipeline.pages
            ),

        "chunks":
            len(
                rag_pipeline.chunks
            ),

        "multimodal":
            True

    })


# ==================================================
# ERROR HANDLER — FILE TOO LARGE
# ==================================================

@app.errorhandler(413)
def request_entity_too_large(error):

    return jsonify({

        "success":
            False,

        "error":
            "The uploaded file is too large. "
            "Maximum allowed size is 50 MB."

    }), 413


# ==================================================
# ERROR HANDLER — GENERAL
# ==================================================

@app.errorhandler(500)
def internal_server_error(error):

    return jsonify({

        "success":
            False,

        "error":
            "Internal server error."

    }), 500


# ==================================================
# RUN FLASK
# ==================================================

if __name__ == "__main__":

    print(
        "\nStarting Document QA RAG application..."
    )

    print(
        "Upload directory:",
        UPLOAD_FOLDER
    )

    print(
        "URL: http://127.0.0.1:5000"
    )

    app.run(

        debug=True,

        use_reloader=False,

        host="127.0.0.1",

        port=5000

    )
from flask import Blueprint, render_template, send_from_directory, jsonify, request, session
from chat_history import create_session, save_message, build_context_for_ai
from scoring import keyword_score
import openai
from detection import detect_grass_type, detect_region, detect_product_need
from query_expansion import expand_query, expand_vague_question
from pinecone import Pinecone
import os
from logging_config import logger

turf_bp = Blueprint('turf_bp', __name__)



@turf_bp.route('/')
def home():
    return render_template('index.html')


@turf_bp.route('/epa_labels/<path:filename>')
def serve_epa_label(filename):
    return send_from_directory('static/epa_labels', filename)


@turf_bp.route('/product-labels/<path:filename>')
def serve_product_label(filename):
    return send_from_directory('static/product-labels', filename)


@turf_bp.route('/solution-sheets/<path:filename>')
def serve_solution_sheet(filename):
    return send_from_directory('static/solution-sheets', filename)


@turf_bp.route('/spray-programs/<path:filename>')
def serve_spray_program(filename):
    return send_from_directory('static/spray-programs', filename)


@turf_bp.route('/ntep-pdfs/<path:filename>')
def serve_ntep(filename):
    return send_from_directory('static/ntep-pdfs', filename)


@turf_bp.route('/resources')
def resources():
    return render_template('resources.html')


@turf_bp.route('/api/resources')
def get_resources():
    resources = []
    folders = {
        'product-labels': 'Product Labels',
        'epa_labels': 'Product Labels',
        'solution-sheets': 'Solution Sheets',
        'spray-programs': 'Spray Programs',
        'ntep-pdfs': 'NTEP Trials'
    }
    try:
        for folder, category in folders.items():
            folder_path = f'static/{folder}'
            if os.path.exists(folder_path):
                for root, dirs, files in os.walk(folder_path):
                    for filename in files:
                        if filename.lower().endswith('.pdf') and not filename.startswith('.'):                            
                            full_path = os.path.join(root, filename)
                            relative_path = full_path.replace('static/', '')
                            resources.append({
                                'filename': filename,
                                'url': f'/static/{relative_path}',
                                'category': category
                            })
        resources.sort(key=lambda x: x['filename'])        
    except Exception as e:
        logger.error(f"Error reading PDF folders: {e}")
        return jsonify({'error': str(e)}), 500
    return jsonify(resources)



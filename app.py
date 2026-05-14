from flask import Flask, render_template, request, redirect, url_for, session, jsonify
from markupsafe import Markup
import sqlite3
import os
from flask import send_from_directory
from urllib.parse import unquote

from werkzeug.utils import secure_filename
UPLOAD_FOLDER = os.path.join(os.path.dirname(__file__), 'uploads', 'reports')
os.makedirs(UPLOAD_FOLDER, exist_ok=True)

app = Flask(__name__)
app.secret_key = 'onecell_dos_secret_2026'

DB_PATH = os.path.join(os.path.dirname(__file__), 'dos.db')

# ─────────────────────────────────────────────────────────────
#  PRODUCT LIST
# ─────────────────────────────────────────────────────────────
TESTS = [
    'OncoIndx TBx',
    'OncoIndx LBx',
    'OncoMonitor TRM',
    'OncoMonitor MRD',
    'OncoIndx Prime Plus',
    'OncoCTC',
    'OncoHRD',
    'OncoRisk',
    'OncoTarget',
    'OncoIndx 360 EC',
]


# ─────────────────────────────────────────────────────────────
#  ACCESS CONTROL — add/remove sections per user type here
# ─────────────────────────────────────────────────────────────
ACL = {
    'Doctor': [
        'instructions', 'dos', 'glossary', 'test_details', 'master_test_directory',
        'biomarker_coverage', 'clinical_positioning', 'performance',
        'support_services', 'journey_mapping', 'comparison',
    ],
    'Patient': [
        'instructions', 'dos', 'glossary', 'test_details', 'biomarker_coverage',
        'clinical_positioning', 'support_services', 'journey_mapping',
        'comparison',
    ],
    'Sales Team': [
        'instructions', 'dos', 'glossary', 'test_details', 'master_test_directory',
        'biomarker_coverage', 'clinical_positioning', 'operations',
        'performance', 'pricing', 'ordering', 'support_services',
        'journey_mapping', 'comparison',
    ],
    'Internal Team': [
        'instructions', 'dos', 'glossary', 'test_details', 'master_test_directory',
        'biomarker_coverage', 'clinical_positioning', 'operations',
        'performance', 'pricing', 'ordering', 'support_services',
        'journey_mapping', 'comparison',
    ],
}
# ─────────────────────────────────────────────────────────────
#  NAVIGATION ITEMS  (key, label, icon)
# ─────────────────────────────────────────────────────────────
NAV_ITEMS = [
    ('dos',                  'DOS',                   'fa-hospital'),
    ('test_details',         'Test Details',          'fa-flask'),
    ('comparison',           'Product Matrix',        'fa-table-columns'),
    ('glossary',             'Glossary',              'fa-spell-check'),

    ('database_header',      'Database',              'fa-database'),

    ('instructions',         'Instructions',          'fa-book-open'),
    ('master_test_directory','Master Test Directory', 'fa-list-alt'),
    ('biomarker_coverage',   'Biomarker Coverage',    'fa-dna'),
    ('clinical_positioning', 'Clinical Positioning',  'fa-stethoscope'),
    ('operations',           'Operations',            'fa-cogs'),
    ('performance',          'Performance',           'fa-chart-line'),
    ('pricing',              'Pricing',               'fa-tags'),
    ('ordering',             'Ordering',              'fa-shopping-cart'),
    ('support_services',     'Support Services',      'fa-headset'),
    ('journey_mapping',      'Journey Mapping',       'fa-route'),
]

# ─────────────────────────────────────────────────────────────
#  COMPARISON TABLE ROW GROUPS
#  Each group has: label, icon, rows[]
#  Each row has:   key (unique DB key), label, hint (optional)
# ─────────────────────────────────────────────────────────────
COMPARISON_ROW_GROUPS = [
    {
        'label': 'Specimen & Sample',
        'icon':  'fa-vial',
        'rows': [
            {'key': 'sample_tissue',       'label': 'Tissue (FFPE Block)',          'hint': 'Core biopsy / surgical resection'},
            {'key': 'sample_blood',        'label': 'Blood (Liquid Biopsy)',         'hint': 'Plasma ctDNA'},
            {'key': 'sample_csf',          'label': 'CSF / Pleural Fluid',           'hint': ''},
            {'key': 'sample_normal_match', 'label': 'Normal Blood Match',            'hint': 'Tissue-Liquid-Normal matched'},
            {'key': 'min_input_dna',       'label': 'Minimum DNA Input',             'hint': 'ng required'},
        ],
    },
    {
        'label': 'Molecular Layer',
        'icon':  'fa-dna',
        'rows': [
            {'key': 'mol_dna',     'label': 'DNA Analysis',                      'hint': 'SNV, INDEL, CNV'},
            {'key': 'mol_rna',     'label': 'RNA Analysis',                       'hint': 'Fusion, splice variants, expression'},
            {'key': 'mol_protein', 'label': 'Protein (IHC)',                      'hint': 'Immunohistochemistry'},
            {'key': 'mol_ctc',     'label': 'Circulating Tumour Cells (CTC)',     'hint': 'Enumeration + PD-L1'},
        ],
    },
    {
        'label': 'Genomic Coverage',
        'icon':  'fa-circle-nodes',
        'rows': [
            {'key': 'genes_covered',      'label': 'Genes Covered',                 'hint': 'Total gene count'},
            {'key': 'exons_covered',      'label': 'Exons (DNA)',                    'hint': 'Number of exons'},
            {'key': 'intronic_regions',   'label': 'Intronic Regions',               'hint': 'Selected intronic coverage'},
            {'key': 'fusion_rna_regions', 'label': 'Fusion-related Regions (RNA)',   'hint': ''},
            {'key': 'genome_backbone',    'label': 'Genome-wide CNV Backbone',       'hint': 'LOH markers'},
            {'key': 'hrd_genes',          'label': 'HRR Genes (HRD)',                'hint': '>50 HRR genes'},
            {'key': 'pgx_markers',        'label': 'Pharmacogenomic Markers',        'hint': 'PGx'},
        ],
    },
    {
        'label': 'Variant Types Detected',
        'icon':  'fa-code-branch',
        'rows': [
            {'key': 'vt_snv',      'label': 'SNV (Single Nucleotide Variants)',   'hint': ''},
            {'key': 'vt_indel',    'label': 'INDEL',                              'hint': 'Insertions & deletions'},
            {'key': 'vt_cna',      'label': 'CNA / CNV',                          'hint': 'Copy number alterations'},
            {'key': 'vt_fusion',   'label': 'Fusions / Translocations',           'hint': 'DNA + RNA based'},
            {'key': 'vt_splice',   'label': 'Splice Variants',                    'hint': 'RNA-based'},
            {'key': 'vt_expr',     'label': 'Gene Expression',                    'hint': 'RNA-based exceptional expression'},
            {'key': 'vt_germline', 'label': 'True Germline Variants',             'hint': 'Separated from somatic'},
            {'key': 'vt_chip',     'label': 'CHIP Mutations',                     'hint': 'Clonal haematopoiesis'},
            {'key': 'vt_reversal', 'label': 'Reversal of Mutation',               'hint': 'Resistance tracking'},
        ],
    },
    {
        'label': 'Clinical Biomarkers',
        'icon':  'fa-microscope',
        'rows': [
            {'key': 'bio_tmb',       'label': 'Tumour Mutation Burden (TMB)',     'hint': 'muts/Mb'},
            {'key': 'bio_msi',       'label': 'Microsatellite Instability (MSI)', 'hint': 'NGS-based'},
            {'key': 'bio_hrd',       'label': 'HRD Score',                        'hint': 'LOH + TAI + LST'},
            {'key': 'bio_pdl1',      'label': 'PD-L1',                            'hint': 'IHC on tissue / CTC'},
            {'key': 'bio_pgx',       'label': 'Pharmacogenomics (PGx)',           'hint': ''},
            {'key': 'bio_ctdna',     'label': 'ctDNA Tumour Fraction',            'hint': '%'},
            {'key': 'bio_ctc_count', 'label': 'CTC Count',                        'hint': 'Enumeration'},
        ],
    },
    {
        'label': 'Technology & Methodology',
        'icon':  'fa-microchip',
        'rows': [
            {'key': 'tech_platform',     'label': 'Sequencing Platform',          'hint': 'e.g. Illumina NextSeq 2000'},
            {'key': 'tech_depth_tissue', 'label': 'Mean Depth — Tissue',          'hint': 'e.g. 2000×'},
            {'key': 'tech_depth_liquid', 'label': 'Mean Depth — Liquid',          'hint': 'e.g. 10000×'},
            {'key': 'tech_umi',          'label': 'UMI-based Error Correction',   'hint': 'Unique Molecular Identifiers'},
            {'key': 'tech_ai',           'label': 'AI / Proprietary Pipeline',    'hint': 'iCare™ or equivalent'},
            {'key': 'tech_ref_genome',   'label': 'Reference Genome',             'hint': 'e.g. GRCh38'},
        ],
    },
    {
        'label': 'Performance Metrics',
        'icon':  'fa-chart-line',
        'rows': [
            {'key': 'perf_sensitivity', 'label': 'Sensitivity (SNV)',             'hint': '%'},
            {'key': 'perf_specificity', 'label': 'Specificity (SNV)',             'hint': '%'},
            {'key': 'perf_ppv',         'label': 'PPV',                           'hint': 'Positive Predictive Value'},
            {'key': 'perf_npv',         'label': 'NPV',                           'hint': 'Negative Predictive Value'},
            {'key': 'perf_lod',         'label': 'Limit of Detection (LOD)',      'hint': 'VAF %'},
            {'key': 'perf_concordance', 'label': 'Concordance',                   'hint': ''},
            {'key': 'perf_fusion_sens', 'label': 'Fusion Sensitivity',            'hint': '%'},
        ],
    },
    {
        'label': 'Accreditation & Compliance',
        'icon':  'fa-shield-halved',
        'rows': [
            {'key': 'acc_cap',  'label': 'CAP Accreditation',                     'hint': 'College of American Pathologists'},
            {'key': 'acc_nabl', 'label': 'NABL Accreditation',                    'hint': 'India'},
            {'key': 'acc_clia', 'label': 'CLIA Certification',                    'hint': 'USA'},
            {'key': 'acc_ce',   'label': 'CE-IVD Mark',                           'hint': 'Europe'},
            {'key': 'acc_fda',  'label': 'FDA Approval',                          'hint': ''},
            {'key': 'acc_dcgi', 'label': 'DCGI Approval',                         'hint': 'India — CTC test'},
        ],
    },
    {
        'label': 'Report & TAT',
        'icon':  'fa-file-medical',
        'rows': [
            {'key': 'rep_tat',          'label': 'Turnaround Time (TAT)',         'hint': 'Working days'},
            {'key': 'rep_format',       'label': 'Report Format',                 'hint': 'PDF / Portal'},
            {'key': 'rep_tiers',        'label': 'Variant Tiering (AMP)',         'hint': 'Tier I–IV'},
            {'key': 'rep_trials',       'label': 'Clinical Trial Matching',       'hint': ''},
            {'key': 'rep_longitudinal', 'label': 'Longitudinal Monitoring',       'hint': 'ctDNA trend'},
        ],
    },
    {
        'label': 'Support Services',
        'icon':  'fa-headset',
        'rows': [
            {'key': 'sup_mtb',     'label': 'Molecular Tumour Board (MTB)',       'hint': ''},
            {'key': 'sup_consult', 'label': 'Post-report Consultation',           'hint': ''},
            {'key': 'sup_rm',      'label': 'Dedicated Relationship Manager',     'hint': ''},
            {'key': 'sup_helpline','label': '1800 Helpline',                      'hint': 'Toll-free India'},
        ],
    },
]


# ─────────────────────────────────────────────────────────────
#  DATABASE HELPERS
# ─────────────────────────────────────────────────────────────
def get_db():
    conn = sqlite3.connect(DB_PATH)
    conn.row_factory = sqlite3.Row
    return conn


def init_db():
    conn = get_db()
    c = conn.cursor()

    c.execute('''CREATE TABLE IF NOT EXISTS master_test_directory (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        test_id TEXT, category TEXT, sub_category TEXT,
        sample_type TEXT, technology TEXT, clinical_use_case TEXT,
        indications TEXT, patient_stage TEXT, line_of_therapy TEXT,
        key_clinical_question TEXT, tat_days TEXT, report_type TEXT, test_status TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS biomarker_coverage (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        biomarker TEXT, variant_type TEXT, clinical_relevance TEXT,
        actionability TEXT, therapy_link TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS clinical_positioning (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        clinical_scenario TEXT, when_to_order TEXT, when_not_to_order TEXT,
        alternative_tests TEXT, competitor_tests TEXT, key_differentiator TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS operations (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        sample_type_detail TEXT, volume_required TEXT, collection_method TEXT,
        stability TEXT, shipping_conditions TEXT, rejection_criteria TEXT, repeat_risk TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS performance (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        sensitivity TEXT, specificity TEXT, concordance TEXT,
        lod TEXT, validation_cohort_size TEXT, cancer_types TEXT, publications TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS pricing (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        list_price TEXT, discount_range TEXT, cost_to_company TEXT,
        gross_margin TEXT, reimbursement_status TEXT, payor_notes TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS ordering (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        test_code TEXT, order_channel TEXT, required_forms TEXT,
        consent_needed TEXT, report_delivery_mode TEXT, tat_commitment TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS support_services (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        tumor_board TEXT, helpline TEXT, post_report_consult TEXT,
        consult_tat TEXT, dedicated_rm TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS journey_mapping (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name TEXT NOT NULL,
        journey_stage TEXT, sub_stage TEXT, fits_as TEXT,
        trigger_event TEXT, gap_indicator TEXT
    )''')

    c.execute('''CREATE TABLE IF NOT EXISTS test_details (
        id                      INTEGER PRIMARY KEY AUTOINCREMENT,
        test_name               TEXT NOT NULL UNIQUE,
        description             TEXT,
        use_case                TEXT,
        category                TEXT,
        sub_category            TEXT,
        technology_stack        TEXT,
        accreditation           TEXT,
        indications             TEXT,
        patient_profile         TEXT,
        clinical_questions      TEXT,
        genes_biomarkers        TEXT,
        variant_types           TEXT,
        competitor_benchmarking TEXT,
        value_proposition       TEXT,
        report_filename         TEXT
    )''')

    # ── Comparison matrix ──────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS comparison_matrix (
        id       INTEGER PRIMARY KEY AUTOINCREMENT,
        row_key  TEXT NOT NULL,
        col_name TEXT NOT NULL,
        value    TEXT,
        UNIQUE(row_key, col_name)
    )''')

    # ── Competitor products ────────────────────────────────────
    c.execute('''CREATE TABLE IF NOT EXISTS comparison_competitors (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT NOT NULL UNIQUE,
        company    TEXT NOT NULL,
        notes      TEXT,
        sort_order INTEGER DEFAULT 0
    )''')
    conn = sqlite3.connect("dos.db")   
    cur = conn.cursor()

    conn.commit()
    conn.close()


def is_admin():
    return session.get('is_admin', False)


def check_access(section):
    user_type = session.get('user_type')
    if not user_type:
        return False
    return section in ACL.get(user_type, [])


# ─────────────────────────────────────────────────────────────
#  CELL RENDERER  (used by comparison table)
# ─────────────────────────────────────────────────────────────
def render_cell(val):
    """Convert a raw DB value into a styled HTML chip."""
    if not val or str(val).strip() in ('', '—', '-'):
        return '<span class="chip-na">—</span>'
    v = str(val).strip().lower()
    if v in ('yes', '✓', 'true', 'y'):
        return '<span class="chip-yes"><i class="fas fa-check"></i> Yes</span>'
    if v in ('no', '✗', 'false', 'n'):
        return '<span class="chip-no"><i class="fas fa-times"></i> No</span>'
    if v in ('partial', '~', 'limited', 'partial yes'):
        return '<span class="chip-partial"><i class="fas fa-minus"></i> Partial</span>'
    return f'<span class="chip-value">{str(val).strip()}</span>'


# ─────────────────────────────────────────────────────────────
#  ROUTES — WELCOME / AUTH
# ─────────────────────────────────────────────────────────────
@app.route('/')
def welcome():
    return render_template('welcome.html')


@app.route('/set_user_type', methods=['POST'])
def set_user_type():
    user_type = request.form.get('user_type')
    if user_type in ACL:
        session['user_type'] = user_type
        return redirect(url_for('instructions'))
    return redirect(url_for('welcome'))


@app.route('/admin/login', methods=['POST'])
def admin_login():
    username = request.form.get('username')
    password = request.form.get('password')
    next_url = request.form.get('next', url_for('instructions'))
    if username == 'admin' and password == 'password':
        session['is_admin'] = True
        return jsonify({'success': True, 'redirect': next_url})
    return jsonify({'success': False, 'message': 'Invalid credentials'})


@app.route('/admin/logout')
def admin_logout():
    session.pop('is_admin', None)
    return redirect(request.referrer or url_for('instructions'))


# ─────────────────────────────────────────────────────────────
#  ROUTE — INSTRUCTIONS
# ─────────────────────────────────────────────────────────────
@app.route('/instructions')
def instructions():
    if not session.get('user_type'):
        return redirect(url_for('welcome'))
    return render_template(
        'instructions.html',
        nav_items=NAV_ITEMS,
        acl=ACL.get(session.get('user_type'), []),
        active='instructions',
    )

@app.route('/dos')
def dos():
    if not session.get('user_type'):
        return redirect(url_for('welcome'))

    dos_rows = [
        ("OncoIndx TBx", "Comprehensive Tissue Genomics", "FFPE Tissue", "7-10 Days"),
        ("OncoIndx LBx", "Liquid Biopsy ctDNA", "Blood", "5-7 Days"),
        ("OncoMonitor TRM", "Therapy Response Monitoring", "Blood", "3-5 Days"),
        ("OncoMonitor MRD", "Minimal Residual Disease", "Blood", "5-7 Days"),
        ("OncoCTC", "CTC Enumeration & Biomarkers", "Blood", "3-5 Days"),
        ("OncoHRD", "HRD Assessment", "FFPE Tissue", "7-10 Days"),
        ("OncoRisk", "Cancer Risk Profiling", "Blood / Saliva", "7 Days"),
        ("OncoTarget", "Targeted Mutation Panel", "FFPE / Blood", "5 Days"),
    ]

    return render_template(
        'dos.html',
        nav_items=NAV_ITEMS,
        acl=ACL.get(session.get('user_type'), []),
        active='dos',
        rows=dos_rows
    )


@app.route('/glossary')
def glossary():
    if not session.get('user_type'):
        return redirect(url_for('welcome'))

    glossary = [
        ("SNV", "Single Nucleotide Variant"),
        ("INDEL", "Insertion or Deletion mutation"),
        ("CNV", "Copy Number Variation"),
        ("VAF", "Variant Allele Frequency"),
        ("TMB", "Tumor Mutational Burden"),
        ("MSI", "Microsatellite Instability"),
        ("HRD", "Homologous Recombination Deficiency"),
        ("CTC", "Circulating Tumor Cells"),
        ("ctDNA", "Circulating tumor DNA"),
        ("NGS", "Next Generation Sequencing"),
        ("FFPE", "Formalin Fixed Paraffin Embedded tissue"),
        ("LOD", "Limit of Detection"),
        ("PD-L1", "Programmed Death Ligand 1"),
        ("RNA", "Ribonucleic Acid"),
        ("DNA", "Deoxyribonucleic Acid"),
        ("Fusion", "Gene rearrangement joining two genes"),
        ("MRD", "Minimal Residual Disease"),
        ("TRM", "Therapy Response Monitoring"),
        ("TAT", "Turnaround Time"),
    ]

    return render_template(
        'glossary.html',
        nav_items=NAV_ITEMS,
        acl=ACL.get(session.get('user_type'), []),
        active='glossary',
        glossary=glossary
    )


# ─────────────────────────────────────────────────────────────
#  ROUTE — TEST DETAILS
# ─────────────────────────────────────────────────────────────
@app.route('/test_details')
def test_details():
    if not check_access('test_details'):
        return redirect(url_for('instructions'))

    selected_test = request.args.get('test', TESTS[0])
    conn = get_db()

    details = conn.execute(
        'SELECT * FROM test_details WHERE test_name=?', (selected_test,)
    ).fetchone()

    master = conn.execute('''
        SELECT category, sub_category, technology, indications, key_clinical_question
        FROM master_test_directory WHERE test_name=? LIMIT 1
    ''', (selected_test,)).fetchone()

    bio = conn.execute('''
        SELECT GROUP_CONCAT(DISTINCT biomarker)    AS biomarkers,
               GROUP_CONCAT(DISTINCT variant_type) AS variants
        FROM biomarker_coverage WHERE test_name=?
    ''', (selected_test,)).fetchone()

    clinical = conn.execute('''
        SELECT clinical_scenario FROM clinical_positioning WHERE test_name=? LIMIT 1
    ''', (selected_test,)).fetchone()

    
    ordering = conn.execute(
        'SELECT * FROM ordering WHERE test_name=? LIMIT 1', (selected_test,)
    ).fetchone()
    ordering = dict(ordering) if ordering else {}
 
    pricing = conn.execute(
        'SELECT * FROM pricing WHERE test_name=? LIMIT 1', (selected_test,)
    ).fetchone()
    pricing = dict(pricing) if pricing else {}
 
    performance = conn.execute(
        'SELECT * FROM performance WHERE test_name=? LIMIT 1', (selected_test,)
    ).fetchone()
    performance = dict(performance) if performance else {}

    conn.close()

    all_fields = [
        'description', 'use_case', 'category', 'sub_category',
        'technology_stack', 'accreditation', 'indications',
        'patient_profile', 'clinical_questions', 'genes_biomarkers',
        'variant_types', 'competitor_benchmarking',
        'value_proposition', 'report_filename',
    ]
    data = {f: (details[f] if details and details[f] else '') for f in all_fields}

    # Auto-fill from related tables only when blank
    if not data['category']           and master:   data['category']           = master['category']              or ''
    if not data['sub_category']       and master:   data['sub_category']       = master['sub_category']          or ''
    if not data['technology_stack']   and master:   data['technology_stack']   = master['technology']            or ''
    if not data['indications']        and master:   data['indications']        = master['indications']           or ''
    if not data['clinical_questions'] and master:   data['clinical_questions'] = master['key_clinical_question'] or ''
    if not data['genes_biomarkers']   and bio:      data['genes_biomarkers']   = bio['biomarkers']               or ''
    if not data['variant_types']      and bio:      data['variant_types']      = bio['variants']                 or ''
    if not data['use_case']           and clinical: data['use_case']           = clinical['clinical_scenario']   or ''

    return render_template(
        'test_details.html',
        nav_items=NAV_ITEMS,
        acl=ACL.get(session.get('user_type'), []),
        active='test_details',
        tests=TESTS,
        selected_test=selected_test,
        details=data,
        ordering=ordering,
        pricing=pricing,
        performance=performance,
    )


@app.route('/test_details/save', methods=['POST'])
def save_test_details():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
    data = request.json
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM test_details WHERE test_name=?', (data['test_name'],)
    ).fetchone()
    fields = [
        'description', 'use_case', 'category', 'sub_category',
        'technology_stack', 'accreditation', 'indications',
        'patient_profile', 'clinical_questions', 'genes_biomarkers',
        'variant_types', 'competitor_benchmarking', 'value_proposition',
    ]
    if existing:
        sets = ', '.join(f'{f}=?' for f in fields)
        vals = [data.get(f, '') for f in fields] + [data['test_name']]
        conn.execute(f'UPDATE test_details SET {sets} WHERE test_name=?', vals)
    else:
        cols = 'test_name, ' + ', '.join(fields)
        qs   = ', '.join(['?'] * (len(fields) + 1))
        vals = [data['test_name']] + [data.get(f, '') for f in fields]
        conn.execute(f'INSERT INTO test_details ({cols}) VALUES ({qs})', vals)
    conn.commit()
    conn.close()
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  ROUTE — PRODUCT COMPARISON TABLE
# ─────────────────────────────────────────────────────────────
@app.route('/comparison')
def comparison():
    if not session.get('user_type'):
        return redirect(url_for('welcome'))

    conn = get_db()

    rows_raw = conn.execute(
        'SELECT row_key, col_name, value FROM comparison_matrix'
    ).fetchall()
    matrix = {}
    for r in rows_raw:
        matrix.setdefault(r['row_key'], {})[r['col_name']] = r['value']

    comps_raw   = conn.execute(
        'SELECT * FROM comparison_competitors ORDER BY sort_order, id'
    ).fetchall()
    competitors = [dict(c) for c in comps_raw]
    conn.close()

    # Expose render_cell to Jinja as a safe filter
    app.jinja_env.globals['render_cell'] = lambda v: Markup(render_cell(v))

    return render_template(
        'comparison.html',
        nav_items=NAV_ITEMS,
        acl=ACL.get(session.get('user_type'), []),
        active='comparison',
        our_products=TESTS,
        competitors=competitors,
        row_groups=COMPARISON_ROW_GROUPS,
        matrix=matrix,
    )


@app.route('/comparison/save', methods=['POST'])
def comparison_save():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
    changes = request.json.get('changes', {})
    conn = get_db()
    for key, value in changes.items():
        try:
            row_key, col_name = key.split('|||')
        except ValueError:
            continue
        conn.execute('''
            INSERT INTO comparison_matrix (row_key, col_name, value)
            VALUES (?, ?, ?)
            ON CONFLICT(row_key, col_name) DO UPDATE SET value = excluded.value
        ''', (row_key, col_name, value))
    conn.commit()
    conn.close()
    return jsonify({'success': True})


@app.route('/comparison/add_competitor', methods=['POST'])
def comparison_add_competitor():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
    data    = request.json
    name    = data.get('name', '').strip()
    company = data.get('company', '').strip()
    notes   = data.get('notes', '').strip()
    if not name or not company:
        return jsonify({'success': False, 'message': 'Name and company are required'})
    conn = get_db()
    try:
        conn.execute(
            'INSERT INTO comparison_competitors (name, company, notes) VALUES (?, ?, ?)',
            (name, company, notes),
        )
        conn.commit()
    except Exception as e:
        conn.close()
        return jsonify({'success': False, 'message': str(e)})
    conn.close()
    return jsonify({'success': True})


@app.route('/comparison/delete_competitor', methods=['POST'])
def comparison_delete_competitor():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
    comp_id = request.json.get('id')
    conn    = get_db()
    comp    = conn.execute(
        'SELECT name FROM comparison_competitors WHERE id=?', (comp_id,)
    ).fetchone()
    if comp:
        conn.execute(
            'DELETE FROM comparison_matrix WHERE col_name=?', (comp['name'],)
        )
    conn.execute('DELETE FROM comparison_competitors WHERE id=?', (comp_id,))
    conn.commit()
    conn.close()
    return jsonify({'success': True})

@app.route('/test_details/upload_report', methods=['POST'])
def upload_report():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
 
    test_name = request.form.get('test_name', '').strip()
    if not test_name:
        return jsonify({'success': False, 'message': 'Test name required'})
 
    file = request.files.get('file')
    if not file or file.filename == '':
        return jsonify({'success': False, 'message': 'No file selected'})
 
    if not file.filename.lower().endswith('.pdf'):
        return jsonify({'success': False, 'message': 'Only PDF files allowed'})
 
    # Save with a safe, predictable filename: TestName.pdf
    safe_name   = secure_filename(test_name) + '.pdf'
    save_path   = os.path.join(UPLOAD_FOLDER, safe_name)
    file.save(save_path)
 
    # Store filename in DB
    conn = get_db()
    existing = conn.execute(
        'SELECT id FROM test_details WHERE test_name=?', (test_name,)
    ).fetchone()
 
    if existing:
        conn.execute(
            'UPDATE test_details SET report_filename=? WHERE test_name=?',
            (safe_name, test_name)
        )
    else:
        conn.execute(
            'INSERT INTO test_details (test_name, report_filename) VALUES (?, ?)',
            (test_name, safe_name)
        )
    conn.commit()
    conn.close()
 
    return jsonify({'success': True, 'filename': safe_name})
 
 
@app.route('/test_details/report/<path:test_name>')
def serve_report(test_name):
    """Serve the uploaded PDF for a given test. Viewable by all logged-in users."""
    if not session.get('user_type'):
        return redirect(url_for('welcome'))
 
    test_name = unquote(test_name)
    conn      = get_db()
    row       = conn.execute(
        'SELECT report_filename FROM test_details WHERE test_name=?', (test_name,)
    ).fetchone()
    conn.close()
 
    if not row or not row['report_filename']:
        return 'No report uploaded for this test.', 404
 
    return send_from_directory(
        UPLOAD_FOLDER,
        row['report_filename'],
        as_attachment=False,           # opens in browser, not download
        mimetype='application/pdf'
    )
 
 
@app.route('/test_details/delete_report', methods=['POST'])
def delete_report():
    if not is_admin():
        return jsonify({'success': False, 'message': 'Unauthorized'})
 
    test_name = request.json.get('test_name', '').strip()
    conn      = get_db()
    row       = conn.execute(
        'SELECT report_filename FROM test_details WHERE test_name=?', (test_name,)
    ).fetchone()
 
    if row and row['report_filename']:
        file_path = os.path.join(UPLOAD_FOLDER, row['report_filename'])
        if os.path.exists(file_path):
            os.remove(file_path)
        conn.execute(
            'UPDATE test_details SET report_filename=NULL WHERE test_name=?',
            (test_name,)
        )
        conn.commit()
 
    conn.close()
    return jsonify({'success': True})


# ─────────────────────────────────────────────────────────────
#  GENERIC SECTION ROUTES  (master_test_directory … journey_mapping)
# ─────────────────────────────────────────────────────────────
def make_section_route(section, table, fields, template):
    def view():
        if not check_access(section):
            return redirect(url_for('instructions'))
        selected_test = request.args.get('test', TESTS[0])
        conn  = get_db()
        rows  = conn.execute(
            f'SELECT * FROM {table} WHERE test_name=?', (selected_test,)
        ).fetchall()
        conn.close()
        return render_template(
            template,
            nav_items=NAV_ITEMS,
            acl=ACL.get(session.get('user_type'), []),
            active=section,
            tests=TESTS,
            selected_test=selected_test,
            rows=rows,
            fields=fields,
        )
    view.__name__ = section
    return view


def make_section_save(section, table, fields):
    def save():
        if not is_admin():
            return jsonify({'success': False, 'message': 'Unauthorized'})
        data      = request.json
        conn      = get_db()
        record_id = data.get('id')
        if record_id:
            sets = ', '.join(f'{f}=?' for f in fields)
            vals = [data.get(f, '') for f in fields] + [record_id]
            conn.execute(f'UPDATE {table} SET {sets} WHERE id=?', vals)
        else:
            cols = 'test_name, ' + ', '.join(fields)
            qs   = ', '.join(['?'] * (len(fields) + 1))
            vals = [data['test_name']] + [data.get(f, '') for f in fields]
            conn.execute(f'INSERT INTO {table} ({cols}) VALUES ({qs})', vals)
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    save.__name__ = f'save_{section}'
    return save


def make_section_delete(section, table):
    def delete():
        if not is_admin():
            return jsonify({'success': False, 'message': 'Unauthorized'})
        record_id = request.json.get('id')
        conn      = get_db()
        conn.execute(f'DELETE FROM {table} WHERE id=?', (record_id,))
        conn.commit()
        conn.close()
        return jsonify({'success': True})
    delete.__name__ = f'delete_{section}'
    return delete


SECTIONS = [
    ('master_test_directory', 'master_test_directory',
     ['test_id', 'category', 'sub_category', 'sample_type', 'technology',
      'clinical_use_case', 'indications', 'patient_stage', 'line_of_therapy',
      'key_clinical_question', 'tat_days', 'report_type', 'test_status'],
     'section_table.html'),

    ('biomarker_coverage', 'biomarker_coverage',
     ['biomarker', 'variant_type', 'clinical_relevance', 'actionability', 'therapy_link'],
     'section_table.html'),

    ('clinical_positioning', 'clinical_positioning',
     ['clinical_scenario', 'when_to_order', 'when_not_to_order',
      'alternative_tests', 'competitor_tests', 'key_differentiator'],
     'section_table.html'),

    ('operations', 'operations',
     ['analyte', 'specimen', 'description',
     'shipping_container', 'acceptance_criteria',
     'shipping_temperature', 'shipping_tat'],
    'section_table.html'),

    ('performance', 'performance',
     ['sensitivity', 'specificity', 'concordance', 'lod',
      'validation_cohort_size', 'cancer_types', 'publications'],
     'section_table.html'),

    ('pricing', 'pricing',
     ['list_price', 'discount_range', 'cost_to_company', 'gross_margin',
      'reimbursement_status', 'payor_notes'],
     'section_table.html'),

    ('ordering', 'ordering',
     ['test_code', 'order_channel', 'required_forms', 'consent_needed',
      'report_delivery_mode', 'tat_commitment'],
     'section_table.html'),

    ('support_services', 'support_services',
     ['tumor_board', 'helpline', 'post_report_consult', 'consult_tat', 'dedicated_rm'],
     'section_table.html'),

    ('journey_mapping', 'journey_mapping',
     ['journey_stage', 'sub_stage', 'fits_as', 'trigger_event', 'gap_indicator'],
     'section_table.html'),
]

for sec, tbl, flds, tmpl in SECTIONS:
    app.add_url_rule(f'/{sec}',        sec,           make_section_route(sec, tbl, flds, tmpl))
    app.add_url_rule(f'/{sec}/save',   f'save_{sec}', make_section_save(sec, tbl, flds),   methods=['POST'])
    app.add_url_rule(f'/{sec}/delete', f'delete_{sec}',make_section_delete(sec, tbl),       methods=['POST'])


# ─────────────────────────────────────────────────────────────
#  ENTRY POINT
# ─────────────────────────────────────────────────────────────
if __name__ == '__main__':
    init_db()
    app.run(debug=True, port=5000)
from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os

app = Flask(__name__)
app.secret_key = 'rattanhouse_secret_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:///rattanhouse.db'
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

ALLOWED = {'png','jpg','jpeg','gif','webp'}

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

# ══════════════════════════════════════════════════
# MODÈLES
# ══════════════════════════════════════════════════

class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    role = db.Column(db.String(20), default='client')
    date_inscription = db.Column(db.DateTime, default=datetime.utcnow)

class Produit(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(200), nullable=False)
    description = db.Column(db.Text)
    caracteristiques = db.Column(db.Text)
    matiere = db.Column(db.String(50))
    prix = db.Column(db.Float, nullable=True)
    type_produit = db.Column(db.String(20), default='standard')
    image = db.Column(db.String(300))
    promotion = db.Column(db.Float, nullable=True)
    actif = db.Column(db.Boolean, default=True)
    date_ajout = db.Column(db.DateTime, default=datetime.utcnow)

class DemandesMesure(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100), nullable=False)
    telephone = db.Column(db.String(20), nullable=False)
    type_produit = db.Column(db.String(100))
    matiere = db.Column(db.String(100))
    description = db.Column(db.Text)
    photo = db.Column(db.Text)  # base64
    date_demande = db.Column(db.DateTime, default=datetime.utcnow)

# ══════════════════════════════════════════════════
# HELPERS
# ══════════════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if session.get('user_role') != 'admin':
            return redirect(url_for('connexion'))
        return f(*a, **kw)
    return dec

# ══════════════════════════════════════════════════
# ROUTES PUBLIQUES
# ══════════════════════════════════════════════════

@app.route('/')
def index():
    produits = Produit.query.filter_by(actif=True).limit(8).all()
    return render_template('index.html', produits=produits)

@app.route('/catalogue')
def catalogue():
    matiere = request.args.get('matiere', '')
    q = Produit.query.filter_by(actif=True)
    if matiere:
        q = q.filter_by(matiere=matiere)
    produits = q.all()
    matieres = [m[0] for m in db.session.query(Produit.matiere).distinct().all() if m[0]]
    return render_template('catalogue.html', produits=produits, matieres=matieres, matiere_active=matiere)

@app.route('/produit/<int:id>')
def produit_detail(id):
    p = Produit.query.get_or_404(id)
    return render_template('produit.html', produit=p)

@app.route('/panier')
def panier():
    return render_template('panier.html')

@app.route('/nos-collections')
def nos_collections():
    return render_template('catalogue_pdf.html')

@app.route('/catalogue-tissus')
def catalogue_tissus():
    return send_from_directory('static', 'catalogue_tissus.pdf')

@app.route('/sur-mesure')
def sur_mesure():
    return render_template('sur_mesure.html')

@app.route('/api/demande-mesure', methods=['POST'])
def api_demande_mesure():
    try:
        data = request.get_json()
        demande = DemandesMesure(
            nom=data.get('nom', ''),
            telephone=data.get('telephone', ''),
            type_produit=data.get('type_produit', ''),
            matiere=data.get('matiere', ''),
            description=data.get('description', ''),
            photo=data.get('photo', None)
        )
        db.session.add(demande)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/session-info')
def session_info():
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'user_nom': session.get('user_nom'),
        'user_role': session.get('user_role'),
    })

# ══════════════════════════════════════════════════
# AUTHENTIFICATION (ADMIN UNIQUEMENT)
# ══════════════════════════════════════════════════

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        d = request.get_json() or request.form
        email = d.get('email', '').strip().lower()
        u = Utilisateur.query.filter_by(email=email).first()
        if u and check_password_hash(u.mot_de_passe, d.get('mot_de_passe', '')):
            session['user_id'] = u.id
            session['user_nom'] = u.nom or u.email
            session['user_role'] = u.role
            return jsonify({'success': True, 'role': u.role})
        return jsonify({'success': False, 'message': 'Email ou mot de passe incorrect'}), 401
    return render_template('connexion.html')

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('index'))

# ══════════════════════════════════════════════════
# ADMIN
# ══════════════════════════════════════════════════

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'produits': Produit.query.filter_by(actif=True).count(),
        'promos': Produit.query.filter(Produit.promotion > 0, Produit.actif==True).count(),
        'matieres': db.session.query(Produit.matiere).distinct().count(),
        'sur_mesure': Produit.query.filter_by(type_produit='mesure', actif=True).count(),
        'demandes': DemandesMesure.query.count(),
    }
    produits_recents = Produit.query.filter_by(actif=True).order_by(Produit.date_ajout.desc()).limit(8).all()
    return render_template('admin/dashboard.html', stats=stats, produits_recents=produits_recents)

@app.route('/admin/produits')
@admin_required
def admin_produits():
    produits = Produit.query.filter_by(actif=True).order_by(Produit.date_ajout.desc()).all()
    return render_template('admin/produits.html', produits=produits, unread=0)

@app.route('/admin/ajouter-produit', methods=['POST'])
@admin_required
def ajouter_produit():
    img = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f"prod_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            img = fn
    tp = request.form.get('type_produit', 'standard')
    prix = None
    if tp == 'standard' and request.form.get('prix'):
        try:
            prix = float(request.form.get('prix'))
        except:
            pass
    p = Produit(
        nom=request.form.get('nom'),
        description=request.form.get('description'),
        caracteristiques=request.form.get('caracteristiques'),
        matiere=request.form.get('matiere'),
        type_produit=tp, prix=prix, image=img
    )
    db.session.add(p)
    db.session.commit()
    return jsonify({'success': True, 'id': p.id})

@app.route('/admin/supprimer-produit/<int:id>', methods=['DELETE'])
@admin_required
def supprimer_produit(id):
    p = Produit.query.get_or_404(id)
    db.session.delete(p)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/promotions', methods=['GET', 'POST'])
@admin_required
def admin_promotions():
    if request.method == 'POST':
        d = request.get_json()
        p = Produit.query.get(d.get('produit_id'))
        if p:
            p.promotion = d.get('reduction')
            db.session.commit()
            return jsonify({'success': True})
    produits = Produit.query.filter_by(actif=True).all()
    return render_template('admin/promotions.html', produits=produits, unread=0)

@app.route('/admin/sur-mesure')
@admin_required
def admin_sur_mesure():
    demandes = DemandesMesure.query.order_by(DemandesMesure.date_demande.desc()).all()
    return render_template('admin/sur_mesure.html', demandes=demandes)

@app.route('/admin/supprimer-demande/<int:id>', methods=['DELETE'])
@admin_required
def admin_supprimer_demande(id):
    demande = DemandesMesure.query.get_or_404(id)
    db.session.delete(demande)
    db.session.commit()
    return jsonify({'success': True})

# ══════════════════════════════════════════════════
# INIT DB
# ══════════════════════════════════════════════════

def init_db():
    db.create_all()
    if not Utilisateur.query.filter_by(role='admin').first():
        db.session.add(Utilisateur(
            nom='Gestionnaire',
            email='admin@rattanhouse.ma',
            mot_de_passe=generate_password_hash('admin123'),
            role='admin'
        ))
        db.session.commit()
        print("Admin cree")

    if Produit.query.count() == 0:
        produits = [
            {'nom':'Salon en rotin exterieur','description':'Salon en rotin ideal pour terrasse.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix':17000,'type_produit':'standard','image':'prod_1.jpg'},
            {'nom':'Lampadaire en rotin','description':'Lampadaire en rotin lumiere douce.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':1000,'type_produit':'standard','image':'prod_2.jpg'},
            {'nom':'Salon en rotin arrondi','description':'Design arrondi elegance et confort.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':14500,'type_produit':'standard','image':'prod_3.jpg'},
            {'nom':'Suspension moderne en rotin','description':'Suspension artistique en rotin.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix':1500,'type_produit':'standard','image':'prod_4.jpg'},
            {'nom':'Suspension design en rotin','description':'Forme sculpturale originale.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':700,'type_produit':'standard','image':'prod_5.jpg'},
            {'nom':'Applique murale en raphia','description':'Applique murale en raphia naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix':150,'type_produit':'standard','image':'prod_6.jpg'},
            {'nom':'Lampadaire en raphia','description':'Lampadaire en raphia.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix':250,'type_produit':'standard','image':'prod_7.jpg'},
            {'nom':'Suspension en raphia','description':'Suspension raphia boheme.','caracteristiques':'Matiere: raphia tresse','matiere':'raphia','prix':900,'type_produit':'standard','image':'prod_8.jpg'},
            {'nom':'Suspension decorative en raphia','description':'Suspension raphia style naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix':250,'type_produit':'standard','image':'prod_9.jpg'},
            {'nom':'Lampe de table en raphia','description':'Lampe table raphia minimaliste.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix':150,'type_produit':'standard','image':'prod_10.jpg'},
            {'nom':'Suspension en fibre naturelle','description':'Suspension fibre naturelle.','caracteristiques':'Matiere: fibre de palmier','matiere':'fibre_palmier','prix':450,'type_produit':'standard','image':'prod_11.jpg'},
            {'nom':'Tabouret en bois et doum','description':'Tabouret artisanal robuste.','caracteristiques':'Matiere: bois et doum','matiere':'doum','prix':60,'type_produit':'standard','image':'prod_12.jpg'},
            {'nom':'Set paniers rangement Doum','description':'Ensemble trois paniers doum.','caracteristiques':'Matiere: fibre doum','matiere':'doum','prix':290,'type_produit':'standard','image':'prod_13.jpg'},
            {'nom':'Main courante en chanvre','description':'Rampe escalier chanvre.','caracteristiques':'Matiere: chanvre | 150 MAD/m','matiere':'corde_chanvre','prix':150,'type_produit':'standard','image':'prod_14.jpg'},
            {'nom':'Suspension chapeau jonc de mer','description':'Luminaire jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prix':450,'type_produit':'standard','image':'prod_15.jpg'},
            {'nom':'Suspension ajouree en doum','description':'Luminaire doum tresse.','caracteristiques':'Matiere: doum','matiere':'doum','prix':240,'type_produit':'standard','image':'prod_16.jpg'},
            {'nom':'Suspension bambou et corde','description':'Lustre bambou et corde.','caracteristiques':'Matiere: bambou et chanvre','matiere':'corde_chanvre','prix':750,'type_produit':'standard','image':'prod_17.jpg'},
            {'nom':'Parasol exotique paille naturelle','description':'Parasol paille ambiance tropicale.','caracteristiques':'Matiere: roseau ou paille','matiere':'roseau','prix':None,'type_produit':'mesure','image':'prod_18.jpg'},
            {'nom':'Suspension Boule Jonc de Mer','description':'Suspension globe jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prix':350,'type_produit':'standard','image':'prod_19.jpg'},
            {'nom':'Rouleau cannage en rotin','description':'Cannage qualite superieure.','caracteristiques':'Matiere: moelle de rotin','matiere':'rotin','prix':400,'type_produit':'standard','image':'prod_20.jpg'},
            {'nom':'Canape Corbeille en Rotin','description':'Canape sculptural rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':8800,'type_produit':'standard','image':'prod_21.jpg'},
            {'nom':'Chaise Paon rotin avec motif','description':'Chaise paon spectaculaire.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix':8000,'type_produit':'standard','image':'prod_22.jpg'},
            {'nom':'Chaise Paon rotin simple','description':'Chaise paon epuree.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':6800,'type_produit':'standard','image':'prod_23.jpg'},
            {'nom':'Chaise longue vintage rotin','description':'Chaise longue vintage.','caracteristiques':'Matiere: rotin et bambou','matiere':'rotin','prix':7000,'type_produit':'standard','image':'prod_24.jpg'},
            {'nom':'Decoration murale raphia','description':'Deco murale raphia soleil.','caracteristiques':'Matiere: raphia et perles bois','matiere':'raphia','prix':180,'type_produit':'standard','image':'prod_25.jpg'},
            {'nom':'Duo plateaux tresses osier','description':'Plateaux ronds osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prix':90,'type_produit':'standard','image':'prod_26.jpg'},
            {'nom':'Ensemble miroirs raphia rotin','description':'Quatre miroirs raphia rotin.','caracteristiques':'Matiere: raphia et rotin','matiere':'raphia','prix':770,'type_produit':'standard','image':'prod_27.jpg'},
            {'nom':'Organisation table en osier','description':'Organisateurs table osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prix':90,'type_produit':'standard','image':'prod_28.jpg'},
            {'nom':'Patere murale en osier','description':'Patere murale osier.','caracteristiques':'Matiere: osier/rotin','matiere':'osier','prix':100,'type_produit':'standard','image':'prod_29.jpg'},
            {'nom':'Pergola en corde de jute','description':'Pergola jute sur mesure.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','prix':None,'type_produit':'mesure','image':'prod_30.jpg'},
            {'nom':'Pergola brise-vue en chaume','description':'Pergola chaume naturel.','caracteristiques':'Matiere: chaume et bois','matiere':'roseau','prix':None,'type_produit':'mesure','image':'prod_31.jpg'},
            {'nom':'Rangement rotin console','description':'Meuble rangement rotin.','caracteristiques':'Matiere: rotin et osier','matiere':'rotin','prix':3400,'type_produit':'standard','image':'prod_32.jpg'},
            {'nom':'Etagere arche en rotin','description':'Etagere arche rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix':4800,'type_produit':'standard','image':'prod_33.jpg'},
            {'nom':'Serie paniers cannage rotin','description':'Trois paniers cannage rotin.','caracteristiques':'Matiere: cannage rotin','matiere':'rotin','prix':2100,'type_produit':'standard','image':'prod_34.jpg'},
            {'nom':'Suspension design rotin noir','description':'Suspension rotin noir.','caracteristiques':'Matiere: rotin noir','matiere':'rotin','prix':700,'type_produit':'standard','image':'prod_35.jpg'},
            {'nom':'Suspension corde jute simple','description':'Suspension jute minimaliste.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','prix':280,'type_produit':'standard','image':'prod_36.jpg'},
            {'nom':'Suspension corde jute decoree','description':'Suspension jute pompons.','caracteristiques':'Matiere: jute et perles bois','matiere':'corde_chanvre','prix':600,'type_produit':'standard','image':'prod_37.jpg'},
            {'nom':'Tabouret de bar en rotin','description':'Tabouret bar rotin moderne.','caracteristiques':'Matiere: rotin et metal','matiere':'rotin','prix':700,'type_produit':'standard','image':'prod_38.jpg'},
        ]
        for p_data in produits:
            db.session.add(Produit(**p_data))
        db.session.commit()
        print(f"OK {len(produits)} produits inseres")

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=False, port=5000)

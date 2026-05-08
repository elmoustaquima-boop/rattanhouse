from flask import Flask, render_template, request, jsonify, session, redirect, url_for, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from werkzeug.security import generate_password_hash, check_password_hash
from werkzeug.utils import secure_filename
from datetime import datetime
from functools import wraps
import os, json

app = Flask(__name__)
app.secret_key = 'rattanhouse_secret_2024'
app.config['SQLALCHEMY_DATABASE_URI'] = 'sqlite:////tmp/rattanhouse.db'
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

ALLOWED = {'png','jpg','jpeg','gif','webp'}

def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

class Utilisateur(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    nom = db.Column(db.String(100))
    email = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    telephone = db.Column(db.String(20))
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

class Devis(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=True)
    mesures = db.Column(db.Text)
    image_modele = db.Column(db.String(300))
    description = db.Column(db.Text)
    montant_estime = db.Column(db.Float, nullable=True)
    statut = db.Column(db.String(30), default='en_attente')
    reponse_gestionnaire = db.Column(db.Text)
    date_demande = db.Column(db.DateTime, default=datetime.utcnow)
    client = db.relationship('Utilisateur', backref='devis')
    produit = db.relationship('Produit', backref='devis')

class Commande(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    client_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    produit_id = db.Column(db.Integer, db.ForeignKey('produit.id'), nullable=True)
    quantite = db.Column(db.Integer, default=1)
    montant_total = db.Column(db.Float)
    statut = db.Column(db.String(30), default='en_preparation')
    mode_livraison = db.Column(db.String(20))
    adresse_livraison = db.Column(db.String(300))
    date_commande = db.Column(db.DateTime, default=datetime.utcnow)
    client = db.relationship('Utilisateur', backref='commandes')
    produit = db.relationship('Produit', backref='commandes')

class Message(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    expediteur_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    destinataire_id = db.Column(db.Integer, db.ForeignKey('utilisateur.id'), nullable=False)
    contenu = db.Column(db.Text, nullable=False)
    lu = db.Column(db.Boolean, default=False)
    date_envoi = db.Column(db.DateTime, default=datetime.utcnow)
    expediteur = db.relationship('Utilisateur', foreign_keys=[expediteur_id])
    destinataire = db.relationship('Utilisateur', foreign_keys=[destinataire_id])

class VisiteSite(db.Model):
    id = db.Column(db.Integer, primary_key=True)
    date = db.Column(db.DateTime, default=datetime.utcnow)
    page = db.Column(db.String(100))

def get_admin():
    return Utilisateur.query.filter_by(role='admin').first()

def track(page):
    try:
        db.session.add(VisiteSite(page=page))
        db.session.commit()
    except:
        db.session.rollback()

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if session.get('user_role') != 'admin':
            return redirect(url_for('connexion'))
        return f(*a, **kw)
    return dec

def login_required_api(f):
    @wraps(f)
    def dec(*a, **kw):
        if 'user_id' not in session:
            return jsonify({'success': False, 'redirect': '/connexion', 'message': 'Connexion requise'}), 401
        return f(*a, **kw)
    return dec

@app.route('/')
def index():
    track('/')
    produits = Produit.query.filter_by(actif=True).limit(8).all()
    return render_template('index.html', produits=produits)

@app.route('/catalogue')
def catalogue():
    track('/catalogue')
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

@app.route('/inscription', methods=['GET', 'POST'])
def inscription():
    if request.method == 'POST':
        d = request.get_json() or request.form
        email = d.get('email', '').strip().lower()
        if not email or not d.get('mot_de_passe'):
            return jsonify({'success': False, 'message': 'Email et mot de passe requis'}), 400
        if Utilisateur.query.filter_by(email=email).first():
            return jsonify({'success': False, 'message': 'Cet email est deja utilise'}), 400
        u = Utilisateur(
            nom=d.get('nom', '').strip(),
            email=email,
            telephone=d.get('telephone', '').strip(),
            mot_de_passe=generate_password_hash(d.get('mot_de_passe', ''))
        )
        db.session.add(u)
        db.session.commit()
        session['user_id'] = u.id
        session['user_nom'] = u.nom or u.email
        session['user_role'] = u.role
        return jsonify({'success': True})
    return render_template('inscription.html')

@app.route('/deconnexion')
def deconnexion():
    session.clear()
    return redirect(url_for('index'))

@app.route('/envoyer-mesures', methods=['POST'])
@login_required_api
def envoyer_mesures():
    mesures = {k: request.form.get(k) for k in ['longueur', 'largeur', 'hauteur', 'notes']}
    dv = Devis(
        client_id=session['user_id'],
        produit_id=request.form.get('produit_id'),
        mesures=json.dumps(mesures),
        statut='en_attente'
    )
    db.session.add(dv)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Mesures envoyees !'})

@app.route('/demander-artisan', methods=['POST'])
@login_required_api
def demander_artisan():
    d = request.get_json() or request.form
    dv = Devis(
        client_id=session['user_id'],
        produit_id=d.get('produit_id'),
        mesures=json.dumps({'type': 'prise_mesure_artisan'}),
        description='Demande de prise de mesure par artisan',
        statut='artisan_requis'
    )
    db.session.add(dv)
    admin = get_admin()
    if admin:
        db.session.add(Message(
            expediteur_id=session['user_id'],
            destinataire_id=admin.id,
            contenu=f"Demande artisan produit #{d.get('produit_id')}"
        ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Demande envoyee !'})

@app.route('/deposer-modele', methods=['POST'])
@login_required_api
def deposer_modele():
    img = None
    if 'image' in request.files:
        f = request.files['image']
        if f and allowed_file(f.filename):
            fn = secure_filename(f"modele_{session['user_id']}_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            img = fn
    dv = Devis(
        client_id=session['user_id'],
        image_modele=img,
        description=request.form.get('description', ''),
        statut='modele_depose'
    )
    db.session.add(dv)
    admin = get_admin()
    if admin:
        db.session.add(Message(
            expediteur_id=session['user_id'],
            destinataire_id=admin.id,
            contenu=f"Nouveau modele: {request.form.get('description', '')[:100]}"
        ))
    db.session.commit()
    return jsonify({'success': True, 'message': 'Modele depose !'})

@app.route('/passer-commande', methods=['POST'])
@login_required_api
def passer_commande():
    d = request.get_json() or request.form
    p = Produit.query.get(d.get('produit_id'))
    if not p:
        return jsonify({'success': False, 'message': 'Produit introuvable'}), 404
    prix = p.prix * (1 - (p.promotion or 0) / 100) if p.prix else 0
    cmd = Commande(
        client_id=session['user_id'],
        produit_id=p.id,
        montant_total=prix,
        mode_livraison=d.get('mode_livraison', 'retrait'),
        adresse_livraison=d.get('adresse', '')
    )
    db.session.add(cmd)
    db.session.commit()
    return jsonify({'success': True, 'message': 'Commande passee !'})

@app.route('/boite-reception')
def boite_reception():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))
    msgs = Message.query.filter_by(destinataire_id=session['user_id']).order_by(Message.date_envoi.desc()).all()
    devis_list = Devis.query.filter_by(client_id=session['user_id']).order_by(Devis.date_demande.desc()).all()
    Message.query.filter_by(destinataire_id=session['user_id'], lu=False).update({'lu': True})
    db.session.commit()
    return render_template('boite_reception.html', messages=msgs, devis_list=devis_list)

@app.route('/envoyer-message', methods=['POST'])
@login_required_api
def envoyer_message():
    d = request.get_json()
    admin = get_admin()
    if not admin:
        return jsonify({'success': False}), 404
    db.session.add(Message(
        expediteur_id=session['user_id'],
        destinataire_id=admin.id,
        contenu=d.get('contenu', '')
    ))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/panier')
def panier():
    return render_template('panier.html')

@app.route('/sur-mesure')
def sur_mesure():
    return render_template('sur_mesure.html')

@app.route('/mes-commandes')
def mes_commandes():
    if 'user_id' not in session:
        return redirect(url_for('connexion'))
    commandes = Commande.query.filter_by(client_id=session['user_id']).order_by(Commande.date_commande.desc()).all()
    return render_template('mes_commandes.html', commandes=commandes)

@app.route('/api/session-info')
def session_info():
    unread = 0
    if 'user_id' in session:
        unread = Message.query.filter_by(destinataire_id=session['user_id'], lu=False).count()
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id': session.get('user_id'),
        'user_nom': session.get('user_nom'),
        'user_role': session.get('user_role'),
        'unread': unread
    })

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = {
        'visites': VisiteSite.query.count(),
        'clients': Utilisateur.query.filter_by(role='client').count(),
        'devis_attente': Devis.query.filter_by(statut='en_attente').count(),
        'commandes': Commande.query.count(),
        'produits': Produit.query.filter_by(actif=True).count(),
    }
    devis_recents = Devis.query.order_by(Devis.date_demande.desc()).limit(5).all()
    commandes_recentes = Commande.query.order_by(Commande.date_commande.desc()).limit(5).all()
    unread = Message.query.filter_by(destinataire_id=session['user_id'], lu=False).count()
    return render_template('admin/dashboard.html', stats=stats, devis=devis_recents,
                           commandes=commandes_recentes, unread=unread)

@app.route('/admin/produits')
@admin_required
def admin_produits():
    produits = Produit.query.order_by(Produit.date_ajout.desc()).all()
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
    p.actif = False
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/devis')
@admin_required
def admin_devis():
    devis_list = Devis.query.order_by(Devis.date_demande.desc()).all()
    return render_template('admin/devis.html', devis_list=devis_list, unread=0)

@app.route('/admin/repondre-devis/<int:id>', methods=['POST'])
@admin_required
def repondre_devis(id):
    dv = Devis.query.get_or_404(id)
    d = request.get_json()
    dv.montant_estime = d.get('montant')
    dv.reponse_gestionnaire = d.get('reponse')
    dv.statut = 'devis_envoye'
    db.session.add(Message(
        expediteur_id=session['user_id'],
        destinataire_id=dv.client_id,
        contenu=f"Votre devis #{id} : {dv.montant_estime} MAD. {dv.reponse_gestionnaire}"
    ))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/messages')
@admin_required
def admin_messages():
    clients = Utilisateur.query.filter_by(role='client').all()
    msgs = Message.query.filter_by(destinataire_id=session['user_id']).order_by(Message.date_envoi.desc()).all()
    Message.query.filter_by(destinataire_id=session['user_id'], lu=False).update({'lu': True})
    db.session.commit()
    return render_template('admin/messages.html', clients=clients, messages=msgs, unread=0)

@app.route('/admin/envoyer-message-client', methods=['POST'])
@admin_required
def envoyer_message_client():
    d = request.get_json()
    db.session.add(Message(
        expediteur_id=session['user_id'],
        destinataire_id=int(d.get('client_id')),
        contenu=d.get('contenu', '')
    ))
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/commandes')
@admin_required
def admin_commandes():
    commandes = Commande.query.order_by(Commande.date_commande.desc()).all()
    return render_template('admin/commandes.html', commandes=commandes, unread=0)

@app.route('/admin/maj-commande/<int:id>', methods=['POST'])
@admin_required
def maj_commande(id):
    cmd = Commande.query.get_or_404(id)
    cmd.statut = request.get_json().get('statut', cmd.statut)
    db.session.commit()
    return jsonify({'success': True})

@app.route('/admin/clients')
@admin_required
def admin_clients():
    clients = Utilisateur.query.filter_by(role='client').order_by(Utilisateur.date_inscription.desc()).all()
    return render_template('admin/clients.html', clients=clients, unread=0)

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

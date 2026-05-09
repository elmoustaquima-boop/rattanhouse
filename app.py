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
# MODÈLES — Cohérents avec le diagramme UML
# ══════════════════════════════════════════════════

# Classe 1 : ResponsableBoutique (= Utilisateur dans le diagramme)
class ResponsableBoutique(db.Model):
    __tablename__ = 'responsable_boutique'
    id             = db.Column(db.Integer, primary_key=True)
    login          = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe   = db.Column(db.String(200), nullable=False)
    nom            = db.Column(db.String(100))
    role           = db.Column(db.String(20), default='admin')
    date_creation  = db.Column(db.DateTime, default=datetime.utcnow)

    def consulter_tableau_de_bord(self):
        return {
            'nb_produits_actifs': Produit.query.filter_by(actif=True).count(),
            'nb_promotions': Produit.query.filter(Produit.promotion_appliquee > 0, Produit.actif==True).count(),
            'nb_demandes_sur_mesure': DemandeSurMesure.query.count(),
        }

    def ajouter_produit(self, nom, matiere, description, image, type_produit, prix=None, promotion=None):
        if type_produit == 'standard':
            p = ProduitStandard(nom=nom, matiere=matiere, description=description,
                               image=image, prix_affiche=prix or 0,
                               promotion_appliquee=promotion or 0)
        else:
            p = ProduitSurMesure(nom=nom, matiere=matiere, description=description, image=image)
        db.session.add(p)
        db.session.commit()
        return p

    def supprimer_produit(self, produit_id):
        p = Produit.query.get(produit_id)
        if p:
            db.session.delete(p)
            db.session.commit()
            return True
        return False

    def appliquer_promotion(self, produit_id, taux):
        p = ProduitStandard.query.get(produit_id)
        if p:
            p.promotion_appliquee = taux
            p.nouveau_prix = p.calculer_nouveau_prix(taux)
            db.session.commit()
            return True
        return False

    def envoyer_devis_whatsapp(self, demande_id):
        d = DemandeSurMesure.query.get(demande_id)
        if d:
            msg = f"Bonjour {d.nom_client} ! Suite a votre demande pour {d.type_produit}, voici notre devis."
            return f"https://wa.me/{d.num_telephone}?text={msg}"
        return None


# Classe 2 : Client
class Client(db.Model):
    __tablename__ = 'client'
    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(100))
    num_telephone = db.Column(db.String(20))
    date_contact  = db.Column(db.DateTime, default=datetime.utcnow)

    def explorer_catalogue(self, matiere=None):
        q = Produit.query.filter_by(actif=True)
        if matiere:
            q = q.filter_by(matiere=matiere)
        return q.all()

    def telecharger_pdf(self, collection):
        if collection == 'produits':
            return '/static/catalogue_rattan_house.pdf'
        elif collection == 'tissus':
            return '/static/catalogue_tissus.pdf'
        return None

    def contacter_assistant_ia(self, message):
        return "https://medjassem.app.n8n.cloud/webhook/e569194a-7069-49a5-b9fc-7ffe8b88a813/chat"


# Classe 3 : Produit (classe de base)
class Produit(db.Model):
    __tablename__ = 'produit'
    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(200), nullable=False)
    matiere       = db.Column(db.String(50))
    description   = db.Column(db.Text)
    caracteristiques = db.Column(db.Text)
    image         = db.Column(db.String(300))
    actif         = db.Column(db.Boolean, default=True)
    type_produit  = db.Column(db.String(20), default='standard')
    date_ajout    = db.Column(db.DateTime, default=datetime.utcnow)
    # Colonnes pour ProduitStandard
    prix_affiche         = db.Column(db.Float, nullable=True)
    promotion_appliquee  = db.Column(db.Float, nullable=True, default=0)
    nouveau_prix         = db.Column(db.Float, nullable=True)
    # Colonne pour ProduitSurMesure
    necessite_devis = db.Column(db.Boolean, default=False)

    __mapper_args__ = {'polymorphic_on': type_produit, 'polymorphic_identity': 'produit'}


# Classe 4 : ProduitStandard (hérite de Produit)
class ProduitStandard(Produit):
    __mapper_args__ = {'polymorphic_identity': 'standard'}

    def calculer_nouveau_prix(self, taux):
        if self.prix_affiche and taux:
            self.nouveau_prix = self.prix_affiche * (1 - taux / 100)
            return self.nouveau_prix
        return self.prix_affiche


# Classe 5 : ProduitSurMesure (hérite de Produit)
class ProduitSurMesure(Produit):
    __mapper_args__ = {'polymorphic_identity': 'mesure'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.necessite_devis = True
        self.prix_affiche = None


# Classe 6 : TableauDeBord
class TableauDeBord(db.Model):
    __tablename__ = 'tableau_de_bord'
    id                    = db.Column(db.Integer, primary_key=True)
    nb_produits_actifs    = db.Column(db.Integer, default=0)
    nb_promotions         = db.Column(db.Integer, default=0)
    nb_demandes_sur_mesure = db.Column(db.Integer, default=0)
    date_mise_a_jour      = db.Column(db.DateTime, default=datetime.utcnow)

    def visualiser_stats(self):
        self.nb_produits_actifs     = Produit.query.filter_by(actif=True).count()
        self.nb_promotions          = Produit.query.filter(Produit.promotion_appliquee > 0, Produit.actif==True).count()
        self.nb_demandes_sur_mesure = DemandeSurMesure.query.count()
        self.date_mise_a_jour       = datetime.utcnow()
        db.session.commit()
        return self


# Classe 7 : Demande (classe de base abstraite)
class Demande(db.Model):
    __tablename__ = 'demande'
    id           = db.Column(db.Integer, primary_key=True)
    date_demande = db.Column(db.DateTime, default=datetime.utcnow)
    statut       = db.Column(db.String(50), default='en_attente')
    type_demande = db.Column(db.String(20))

    __mapper_args__ = {'polymorphic_on': type_demande, 'polymorphic_identity': 'demande'}

    def envoyer_via_whatsapp(self):
        raise NotImplementedError


# Classe 8 : CommandeStandard (hérite de Demande)
class CommandeStandard(Demande):
    __tablename__ = 'commande_standard'
    id         = db.Column(db.Integer, db.ForeignKey('demande.id'), primary_key=True)
    prix_total = db.Column(db.Float, default=0.0)
    produits_json = db.Column(db.Text)  # liste produits en JSON

    __mapper_args__ = {'polymorphic_identity': 'standard'}

    def envoyer_via_whatsapp(self):
        msg = f"Bonjour Rattan House ! Je souhaite commander. Total: {self.prix_total} MAD"
        return f"https://wa.me/212669952693?text={msg}"


# Classe 9 : DemandeSurMesure (hérite de Demande)
class DemandeSurMesure(Demande):
    __tablename__ = 'demande_sur_mesure'
    id                   = db.Column(db.Integer, db.ForeignKey('demande.id'), primary_key=True)
    nom_client           = db.Column(db.String(100), nullable=False)
    num_telephone        = db.Column(db.String(20), nullable=False)
    type_produit         = db.Column(db.String(100))
    matiere_souhaitee    = db.Column(db.String(100))
    description_specifique = db.Column(db.Text)
    photo_modele         = db.Column(db.Text)  # base64
    option_passage_artisan = db.Column(db.Boolean, default=False)

    __mapper_args__ = {'polymorphic_identity': 'sur_mesure'}

    def envoyer_via_whatsapp(self):
        msg = f"Bonjour ! Demande sur mesure de {self.nom_client} pour {self.type_produit}"
        return f"https://wa.me/212669952693?text={msg}"

    def uploader_photo(self, photo_base64):
        self.photo_modele = photo_base64
        db.session.commit()

    def envoyer_demande(self):
        self.statut = 'envoyee'
        db.session.commit()
        return True


# Classe 10 : AssistantIA
class AssistantIA(db.Model):
    __tablename__ = 'assistant_ia'
    id          = db.Column(db.Integer, primary_key=True)
    webhook_url = db.Column(db.String(500), default='https://medjassem.app.n8n.cloud/webhook/e569194a-7069-49a5-b9fc-7ffe8b88a813/chat')
    session_id  = db.Column(db.String(100))

    def traiter_requete(self, message):
        return {'webhook': self.webhook_url, 'message': message}

    def generer_reponse(self, reponse_ia):
        return reponse_ia


# Classe 11 : CataloguePDF
class CataloguePDF(db.Model):
    __tablename__ = 'catalogue_pdf'
    id          = db.Column(db.Integer, primary_key=True)
    fichier_url = db.Column(db.String(300))
    type        = db.Column(db.String(50))  # 'Tissus' ou 'Produits'
    nb_pages    = db.Column(db.Integer)

    def visualiser(self):
        return self.fichier_url

    def telecharger(self):
        return self.fichier_url


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
        demande = DemandeSurMesure(
            nom_client=data.get('nom', ''),
            num_telephone=data.get('telephone', ''),
            type_produit=data.get('type_produit', ''),
            matiere_souhaitee=data.get('matiere', ''),
            description_specifique=data.get('description', ''),
            photo_modele=data.get('photo', None),
            option_passage_artisan=data.get('option_artisan', False)
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
# AUTHENTIFICATION
# ══════════════════════════════════════════════════

@app.route('/connexion', methods=['GET', 'POST'])
def connexion():
    if request.method == 'POST':
        d = request.get_json() or request.form
        login = d.get('email', '').strip().lower()
        u = ResponsableBoutique.query.filter_by(login=login).first()
        if u and check_password_hash(u.mot_de_passe, d.get('mot_de_passe', '')):
            session['user_id']   = u.id
            session['user_nom']  = u.nom or u.login
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
        'promos': Produit.query.filter(Produit.promotion_appliquee > 0, Produit.actif==True).count(),
        'matieres': db.session.query(Produit.matiere).distinct().count(),
        'sur_mesure': ProduitSurMesure.query.filter_by(actif=True).count(),
        'demandes': DemandeSurMesure.query.count(),
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
    responsable = ResponsableBoutique.query.get(session['user_id'])
    img = None
    if 'image' in request.files:
        f = request.files['image']
        if f and f.filename and allowed_file(f.filename):
            fn = secure_filename(f"prod_{int(datetime.utcnow().timestamp())}_{f.filename}")
            f.save(os.path.join(app.config['UPLOAD_FOLDER'], fn))
            img = fn
    tp = request.form.get('type_produit', 'standard')
    prix = None
    if request.form.get('prix'):
        try: prix = float(request.form.get('prix'))
        except: pass
    responsable.ajouter_produit(
        nom=request.form.get('nom'),
        matiere=request.form.get('matiere'),
        description=request.form.get('description'),
        image=img,
        type_produit=tp,
        prix=prix
    )
    return jsonify({'success': True})

@app.route('/admin/supprimer-produit/<int:id>', methods=['DELETE'])
@admin_required
def supprimer_produit(id):
    responsable = ResponsableBoutique.query.get(session['user_id'])
    success = responsable.supprimer_produit(id)
    return jsonify({'success': success})

@app.route('/admin/promotions', methods=['GET', 'POST'])
@admin_required
def admin_promotions():
    if request.method == 'POST':
        d = request.get_json()
        responsable = ResponsableBoutique.query.get(session['user_id'])
        responsable.appliquer_promotion(d.get('produit_id'), d.get('reduction', 0))
        return jsonify({'success': True})
    produits = Produit.query.filter_by(actif=True).all()
    return render_template('admin/promotions.html', produits=produits, unread=0)

@app.route('/admin/sur-mesure')
@admin_required
def admin_sur_mesure():
    demandes = DemandeSurMesure.query.order_by(DemandeSurMesure.date_demande.desc()).all()
    return render_template('admin/sur_mesure.html', demandes=demandes)

@app.route('/admin/supprimer-demande/<int:id>', methods=['DELETE'])
@admin_required
def admin_supprimer_demande(id):
    demande = DemandeSurMesure.query.get_or_404(id)
    db.session.delete(demande)
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════
# INIT DB
# ══════════════════════════════════════════════════

def init_db():
    db.create_all()

    # Créer le responsable boutique (admin)
    if not ResponsableBoutique.query.filter_by(role='admin').first():
        db.session.add(ResponsableBoutique(
            nom='Gestionnaire',
            login='admin@rattanhouse.ma',
            mot_de_passe=generate_password_hash('admin123'),
            role='admin'
        ))
        db.session.commit()
        print("ResponsableBoutique cree")

    # Créer les catalogues PDF
    if CataloguePDF.query.count() == 0:
        db.session.add(CataloguePDF(fichier_url='/static/catalogue_rattan_house.pdf', type='Produits', nb_pages=16))
        db.session.add(CataloguePDF(fichier_url='/static/catalogue_tissus.pdf', type='Tissus', nb_pages=10))
        db.session.commit()
        print("CataloguesPDF crees")

    # Créer les produits
    if Produit.query.count() == 0:
        produits_standard = [
            {'nom':'Salon en rotin exterieur','description':'Salon en rotin ideal pour terrasse.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix_affiche':17000,'image':'prod_1.jpg'},
            {'nom':'Lampadaire en rotin','description':'Lampadaire en rotin lumiere douce.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':1000,'image':'prod_2.jpg'},
            {'nom':'Salon en rotin arrondi','description':'Design arrondi elegance et confort.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':14500,'image':'prod_3.jpg'},
            {'nom':'Suspension moderne en rotin','description':'Suspension artistique en rotin.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix_affiche':1500,'image':'prod_4.jpg'},
            {'nom':'Suspension design en rotin','description':'Forme sculpturale originale.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':700,'image':'prod_5.jpg'},
            {'nom':'Applique murale en raphia','description':'Applique murale en raphia naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix_affiche':150,'image':'prod_6.jpg'},
            {'nom':'Lampadaire en raphia','description':'Lampadaire en raphia.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix_affiche':250,'image':'prod_7.jpg'},
            {'nom':'Suspension en raphia','description':'Suspension raphia boheme.','caracteristiques':'Matiere: raphia tresse','matiere':'raphia','prix_affiche':900,'image':'prod_8.jpg'},
            {'nom':'Suspension decorative en raphia','description':'Suspension raphia style naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix_affiche':250,'image':'prod_9.jpg'},
            {'nom':'Lampe de table en raphia','description':'Lampe table raphia minimaliste.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prix_affiche':150,'image':'prod_10.jpg'},
            {'nom':'Suspension en fibre naturelle','description':'Suspension fibre naturelle.','caracteristiques':'Matiere: fibre de palmier','matiere':'fibre_palmier','prix_affiche':450,'image':'prod_11.jpg'},
            {'nom':'Tabouret en bois et doum','description':'Tabouret artisanal robuste.','caracteristiques':'Matiere: bois et doum','matiere':'doum','prix_affiche':60,'image':'prod_12.jpg'},
            {'nom':'Set paniers rangement Doum','description':'Ensemble trois paniers doum.','caracteristiques':'Matiere: fibre doum','matiere':'doum','prix_affiche':290,'image':'prod_13.jpg'},
            {'nom':'Main courante en chanvre','description':'Rampe escalier chanvre.','caracteristiques':'Matiere: chanvre','matiere':'corde_chanvre','prix_affiche':150,'image':'prod_14.jpg'},
            {'nom':'Suspension chapeau jonc de mer','description':'Luminaire jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prix_affiche':450,'image':'prod_15.jpg'},
            {'nom':'Suspension ajouree en doum','description':'Luminaire doum tresse.','caracteristiques':'Matiere: doum','matiere':'doum','prix_affiche':240,'image':'prod_16.jpg'},
            {'nom':'Suspension bambou et corde','description':'Lustre bambou et corde.','caracteristiques':'Matiere: bambou et chanvre','matiere':'corde_chanvre','prix_affiche':750,'image':'prod_17.jpg'},
            {'nom':'Suspension Boule Jonc de Mer','description':'Suspension globe jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prix_affiche':350,'image':'prod_19.jpg'},
            {'nom':'Rouleau cannage en rotin','description':'Cannage qualite superieure.','caracteristiques':'Matiere: moelle de rotin','matiere':'rotin','prix_affiche':400,'image':'prod_20.jpg'},
            {'nom':'Canape Corbeille en Rotin','description':'Canape sculptural rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':8800,'image':'prod_21.jpg'},
            {'nom':'Chaise Paon rotin avec motif','description':'Chaise paon spectaculaire.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prix_affiche':8000,'image':'prod_22.jpg'},
            {'nom':'Chaise Paon rotin simple','description':'Chaise paon epuree.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':6800,'image':'prod_23.jpg'},
            {'nom':'Chaise longue vintage rotin','description':'Chaise longue vintage.','caracteristiques':'Matiere: rotin et bambou','matiere':'rotin','prix_affiche':7000,'image':'prod_24.jpg'},
            {'nom':'Decoration murale raphia','description':'Deco murale raphia soleil.','caracteristiques':'Matiere: raphia et perles bois','matiere':'raphia','prix_affiche':180,'image':'prod_25.jpg'},
            {'nom':'Duo plateaux tresses osier','description':'Plateaux ronds osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prix_affiche':90,'image':'prod_26.jpg'},
            {'nom':'Ensemble miroirs raphia rotin','description':'Quatre miroirs raphia rotin.','caracteristiques':'Matiere: raphia et rotin','matiere':'raphia','prix_affiche':770,'image':'prod_27.jpg'},
            {'nom':'Organisation table en osier','description':'Organisateurs table osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prix_affiche':90,'image':'prod_28.jpg'},
            {'nom':'Patere murale en osier','description':'Patere murale osier.','caracteristiques':'Matiere: osier/rotin','matiere':'osier','prix_affiche':100,'image':'prod_29.jpg'},
            {'nom':'Rangement rotin console','description':'Meuble rangement rotin.','caracteristiques':'Matiere: rotin et osier','matiere':'rotin','prix_affiche':3400,'image':'prod_32.jpg'},
            {'nom':'Etagere arche en rotin','description':'Etagere arche rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prix_affiche':4800,'image':'prod_33.jpg'},
            {'nom':'Serie paniers cannage rotin','description':'Trois paniers cannage rotin.','caracteristiques':'Matiere: cannage rotin','matiere':'rotin','prix_affiche':2100,'image':'prod_34.jpg'},
            {'nom':'Suspension design rotin noir','description':'Suspension rotin noir.','caracteristiques':'Matiere: rotin noir','matiere':'rotin','prix_affiche':700,'image':'prod_35.jpg'},
            {'nom':'Suspension corde jute simple','description':'Suspension jute minimaliste.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','prix_affiche':280,'image':'prod_36.jpg'},
            {'nom':'Suspension corde jute decoree','description':'Suspension jute pompons.','caracteristiques':'Matiere: jute et perles bois','matiere':'corde_chanvre','prix_affiche':600,'image':'prod_37.jpg'},
            {'nom':'Tabouret de bar en rotin','description':'Tabouret bar rotin moderne.','caracteristiques':'Matiere: rotin et metal','matiere':'rotin','prix_affiche':700,'image':'prod_38.jpg'},
        ]
        produits_mesure = [
            {'nom':'Parasol exotique paille naturelle','description':'Parasol paille ambiance tropicale.','caracteristiques':'Matiere: roseau ou paille','matiere':'roseau','image':'prod_18.jpg'},
            {'nom':'Pergola en corde de jute','description':'Pergola jute sur mesure.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','image':'prod_30.jpg'},
            {'nom':'Pergola brise-vue en chaume','description':'Pergola chaume naturel.','caracteristiques':'Matiere: chaume et bois','matiere':'roseau','image':'prod_31.jpg'},
        ]
        for p_data in produits_standard:
            db.session.add(ProduitStandard(**p_data))
        for p_data in produits_mesure:
            db.session.add(ProduitSurMesure(**p_data))
        db.session.commit()
        print(f"OK {len(produits_standard)+len(produits_mesure)} produits inseres")

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=False, port=5000)

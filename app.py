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
app.config['SQLALCHEMY_TRACK_MODIFICATIONS'] = False
app.config['UPLOAD_FOLDER'] = os.path.join('static', 'uploads')
app.config['MAX_CONTENT_LENGTH'] = 16 * 1024 * 1024
os.makedirs(app.config['UPLOAD_FOLDER'], exist_ok=True)
db = SQLAlchemy(app)

ALLOWED = {'png','jpg','jpeg','gif','webp'}
def allowed_file(fn):
    return '.' in fn and fn.rsplit('.',1)[1].lower() in ALLOWED

# ══════════════════════════════════════════════════════════════════
# 13 CLASSES 
# ══════════════════════════════════════════════════════════════════

# ─── CLASSE 1 : ResponsableBoutique ───────────────────────────────
class ResponsableBoutique(db.Model):
    """Gestionnaire du site — accès au tableau de bord admin"""
    __tablename__ = 'responsable_boutique'
    id           = db.Column(db.Integer, primary_key=True)
    login        = db.Column(db.String(120), unique=True, nullable=False)
    mot_de_passe = db.Column(db.String(200), nullable=False)
    nom          = db.Column(db.String(100))
    role         = db.Column(db.String(20), default='admin')

    def consulterTableauDeBord(self):
        return TableauDeBord.get_stats()

    def ajouterProduit(self, nom, matiere, description, image, type_produit, prix=None):
        if type_produit == 'standard':
            p = ProduitStandard(nom=nom, matiere=matiere, description=description,
                                image=image, prixAffiche=prix or 0, promotionAppliquee=0)
        else:
            p = ProduitSurMesure(nom=nom, matiere=matiere, description=description, image=image)
        db.session.add(p)
        db.session.commit()
        return p

    def modifierProduit(self, produit_id, **kwargs):
        p = Produit.query.get(produit_id)
        if p:
            for k, v in kwargs.items():
                setattr(p, k, v)
            db.session.commit()
            return True
        return False

    def supprimerProduit(self, produit_id):
        p = Produit.query.get(produit_id)
        if p:
            db.session.delete(p)
            db.session.commit()
            return True
        return False

    def appliquerPromotion(self, produit_id, taux):
        p = Produit.query.get(produit_id)
        if p and p.type_produit == 'standard':
            p.promotionAppliquee = taux
            p.nouveauPrix = p.prixAffiche * (1 - taux / 100) if taux else p.prixAffiche
            db.session.commit()
            return True
        return False

    def envoyerDevisWhatsApp(self, surMesure_id):
        sm = SurMesure.query.get(surMesure_id)
        if sm:
            num = sm.numTelephone.replace('+','').replace(' ','').replace('-','')
            msg = (f"Bonjour {sm.nomClient} ! 🌿\n"
                   f"Suite à votre demande pour {sm.typeProduit},\n"
                   f"voici notre devis :\n\n"
                   f"💰 Prix : ___ MAD\n"
                   f"📦 Délai : ___ jours\n"
                   f"🚚 Livraison : ___ MAD\n\n"
                   f"Merci de confirmer 🙏")
            return f"https://wa.me/{num}?text={msg}"
        return None


# ─── CLASSE 2 : TableauDeBord ────────────────────────────────────
class TableauDeBord(db.Model):
    """Statistiques du site visibles dans l'interface admin"""
    __tablename__ = 'tableau_de_bord'
    id                    = db.Column(db.Integer, primary_key=True)
    nbProduitsActifs      = db.Column(db.Integer, default=0)
    nbPromotions          = db.Column(db.Integer, default=0)
    nbProduitsSurMesure   = db.Column(db.Integer, default=0)
    nbDemandesSurMesure   = db.Column(db.Integer, default=0)

    @staticmethod
    def get_stats():
        return {
            'produits':   Produit.query.filter_by(estActif=True).count(),
            'promos':     Produit.query.filter(Produit.promotionAppliquee > 0, Produit.estActif==True).count(),
            'matieres':   db.session.query(Produit.matiere).distinct().count(),
            'sur_mesure': Produit.query.filter_by(type_produit='mesure', estActif=True).count(),
            'demandes':   SurMesure.query.count(),
        }

    def visualiserProduitsActifs(self):
        return Produit.query.filter_by(estActif=True).count()

    def visualiserPromotions(self):
        return Produit.query.filter(Produit.promotionAppliquee > 0, Produit.estActif==True).count()

    def visualiserProduitsSurMesure(self):
        return Produit.query.filter_by(type_produit='mesure', estActif=True).count()

    def visualiserDemandesSurMesure(self):
        return SurMesure.query.count()


# ─── CLASSE 3 : Client ───────────────────────────────────────────
class Client(db.Model):
    """Visiteur du site — commande via WhatsApp sans compte"""
    __tablename__ = 'client'
    id            = db.Column(db.Integer, primary_key=True)
    nom           = db.Column(db.String(100))
    numTelephone  = db.Column(db.String(20))

    def consulterAccueil(self):
        return Produit.query.filter_by(estActif=True).limit(8).all()

    def decouvririCollection(self):
        return Produit.query.filter_by(estActif=True).all()

    def explorerCatalogue(self):
        return Produit.query.filter_by(estActif=True).all()

    def filtrerProduits(self, matiere):
        return Produit.query.filter_by(estActif=True, matiere=matiere).all()

    def telechargerPDF(self, collection):
        c = CataloguePDF.query.filter_by(type=collection).first()
        return c.telecharger() if c else None

    def contacterAssistantIA(self, message):
        ia = AssistantIA.query.first()
        return ia.traiterRequete(message) if ia else None

    def suivreInstagram(self):
        return 'https://instagram.com/rattanhousema'

    def trouverLocalisation(self):
        return 'https://maps.app.goo.gl/8ubzZqYeDKVKZrXM9'


# ─── CLASSE 4 : Panier ───────────────────────────────────────────
class Panier(db.Model):
    """Panier client — géré aussi en localStorage JavaScript"""
    __tablename__ = 'panier'
    id            = db.Column(db.Integer, primary_key=True)
    session_id    = db.Column(db.String(100))
    total         = db.Column(db.Float, default=0.0)
    produits_json = db.Column(db.Text, default='[]')

    def ajouterProduit(self, produit_id, quantite=1):
        produits = json.loads(self.produits_json or '[]')
        for item in produits:
            if item['id'] == produit_id:
                item['quantite'] += quantite
                self.produits_json = json.dumps(produits)
                self.total = self.calculerTotal()
                db.session.commit()
                return
        p = Produit.query.get(produit_id)
        if p:
            produits.append({'id': produit_id, 'nom': p.nom,
                            'prix': p.prixAffiche, 'quantite': quantite})
            self.produits_json = json.dumps(produits)
            self.total = self.calculerTotal()
            db.session.commit()

    def supprimerProduit(self, produit_id):
        produits = json.loads(self.produits_json or '[]')
        self.produits_json = json.dumps([p for p in produits if p['id'] != produit_id])
        self.total = self.calculerTotal()
        db.session.commit()

    def calculerTotal(self):
        produits = json.loads(self.produits_json or '[]')
        return sum(p.get('prix', 0) * p.get('quantite', 1) for p in produits)

    def commanderViaWhatsApp(self):
        produits = json.loads(self.produits_json or '[]')
        msg = "Bonjour Rattan House ! 🌿\nJe souhaite commander :\n\n"
        for p in produits:
            msg += f"• {p['nom']} x{p.get('quantite',1)}\n"
        msg += f"\nTotal : {self.calculerTotal()} MAD\nMerci !"
        return f"https://wa.me/212669952693?text={msg}"


# ─── CLASSE 5 : Produit (classe abstraite) ───────────────────────
class Produit(db.Model):
    """Classe de base pour tous les produits du catalogue"""
    __tablename__ = 'produit'
    id               = db.Column(db.Integer, primary_key=True)
    nom              = db.Column(db.String(200), nullable=False)
    matiere          = db.Column(db.String(50))
    description      = db.Column(db.Text)
    caracteristiques = db.Column(db.Text)
    image            = db.Column(db.String(300))
    estActif         = db.Column(db.Boolean, default=True)
    type_produit     = db.Column(db.String(20), default='standard')
    date_ajout       = db.Column(db.DateTime, default=datetime.utcnow)
    # Champs ProduitStandard
    prixAffiche        = db.Column(db.Float, nullable=True)
    promotionAppliquee = db.Column(db.Float, nullable=True, default=0)
    nouveauPrix        = db.Column(db.Float, nullable=True)
    # Champ ProduitSurMesure
    necessiteDevis = db.Column(db.Boolean, default=False)

    __mapper_args__ = {'polymorphic_on': type_produit, 'polymorphic_identity': 'produit'}


# ─── CLASSE 6 : ProduitStandard (hérite de Produit) ──────────────
class ProduitStandard(Produit):
    """Produit à prix fixe avec possibilité de promotion"""
    __mapper_args__ = {'polymorphic_identity': 'standard'}

    def calculerNouveauPrix(self, taux):
        if self.prixAffiche and taux:
            self.nouveauPrix = self.prixAffiche * (1 - taux / 100)
            db.session.commit()
            return self.nouveauPrix
        return self.prixAffiche


# ─── CLASSE 7 : ProduitSurMesure (hérite de Produit) ─────────────
class ProduitSurMesure(Produit):
    """Produit nécessitant un devis — prix sur demande"""
    __mapper_args__ = {'polymorphic_identity': 'mesure'}

    def __init__(self, **kwargs):
        super().__init__(**kwargs)
        self.necessiteDevis = True
        self.prixAffiche = None


# ─── CLASSE 8 : SurMesure ────────────────────────────────────────
class SurMesure(db.Model):
    """Demande sur mesure soumise par un client"""
    __tablename__ = 'sur_mesure'
    id                = db.Column(db.Integer, primary_key=True)
    nomClient         = db.Column(db.String(100), nullable=False)
    numTelephone      = db.Column(db.String(20), nullable=False)
    typeProduit       = db.Column(db.String(100))
    matiereSouhaitee  = db.Column(db.String(100))
    description       = db.Column(db.Text)
    photoModele       = db.Column(db.Text)  # base64
    statut            = db.Column(db.String(50), default='en_attente')
    date_demande      = db.Column(db.DateTime, default=datetime.utcnow)

    def uploaderPhoto(self, photo_base64):
        """Enregistre la photo de référence encodée en base64"""
        self.photoModele = photo_base64
        db.session.commit()

    def envoyerDemande(self):
        """Marque la demande comme envoyée"""
        self.statut = 'envoyee'
        db.session.commit()
        return True


# ─── CLASSE 9 : Commande (classe abstraite) ──────────────────────
class Commande(db.Model):
    """Classe de base abstraite pour les commandes"""
    __tablename__ = 'commande'
    id           = db.Column(db.Integer, primary_key=True)
    date_commande = db.Column(db.DateTime, default=datetime.utcnow)
    statut        = db.Column(db.String(50), default='en_attente')
    type_commande = db.Column(db.String(20))

    __mapper_args__ = {'polymorphic_on': type_commande, 'polymorphic_identity': 'commande'}

    def envoyerViaWhatsApp(self):
        raise NotImplementedError("Implémenter dans la sous-classe")


# ─── CLASSE 10 : CommandeStandard (hérite de Commande) ───────────
class CommandeStandard(Commande):
    """Commande standard passée via le panier"""
    __tablename__ = 'commande_standard'
    id            = db.Column(db.Integer, db.ForeignKey('commande.id'), primary_key=True)
    prixTotal     = db.Column(db.Float, default=0.0)
    listeProduits = db.Column(db.Text, default='[]')

    __mapper_args__ = {'polymorphic_identity': 'standard'}

    def confirmerViaWhatsApp(self):
        """Génère le message WhatsApp pour confirmer la commande"""
        produits = json.loads(self.listeProduits or '[]')
        msg = "Bonjour Rattan House ! 🌿\nJe souhaite commander :\n\n"
        for p in produits:
            msg += f"• {p.get('nom','')} x{p.get('quantite',1)}\n"
        msg += f"\nTotal : {self.prixTotal} MAD\nMerci !"
        return f"https://wa.me/212669952693?text={msg}"

    def envoyerViaWhatsApp(self):
        return self.confirmerViaWhatsApp()


# ─── CLASSE 11 : CommandeSurMesure (hérite de Commande) ──────────
class CommandeSurMesure(Commande):
    """Commande sur mesure avec description spécifique"""
    __tablename__ = 'commande_sur_mesure'
    id                    = db.Column(db.Integer, db.ForeignKey('commande.id'), primary_key=True)
    descriptionSpecifique = db.Column(db.Text)
    optionPassageArtisan  = db.Column(db.Boolean, default=False)

    __mapper_args__ = {'polymorphic_identity': 'sur_mesure'}

    def demanderPassageArtisan(self):
        """Active l'option de passage d'un artisan"""
        self.optionPassageArtisan = True
        db.session.commit()
        return True

    def envoyerDescriptionWhatsApp(self):
        """Envoie la description spécifique via WhatsApp"""
        msg = (f"Bonjour Rattan House ! 🌿\n"
               f"Description spécifique :\n{self.descriptionSpecifique}\n\n"
               f"Option artisan : {'Oui' if self.optionPassageArtisan else 'Non'}")
        return f"https://wa.me/212669952693?text={msg}"

    def envoyerViaWhatsApp(self):
        return self.envoyerDescriptionWhatsApp()


# ─── CLASSE 12 : AssistantIA ─────────────────────────────────────
class AssistantIA(db.Model):
    """Assistant IA intégré via webhook n8n"""
    __tablename__ = 'assistant_ia'
    id          = db.Column(db.Integer, primary_key=True)
    webhook_url = db.Column(db.String(500),
        default='https://medjassem.app.n8n.cloud/webhook/e569194a-7069-49a5-b9fc-7ffe8b88a813/chat')

    def traiterRequete(self, message):
        return {'webhook': self.webhook_url, 'chatInput': message}

    def genererReponse(self, reponse_ia):
        return reponse_ia.get('output') or reponse_ia.get('text') or "Désolé, je n'ai pas compris."


# ─── CLASSE 13 : CataloguePDF ────────────────────────────────────
class CataloguePDF(db.Model):
    """Catalogue PDF téléchargeable — Produits ou Tissus"""
    __tablename__ = 'catalogue_pdf'
    id          = db.Column(db.Integer, primary_key=True)
    type        = db.Column(db.String(50))
    fichierUrl  = db.Column(db.String(300))
    nb_pages    = db.Column(db.Integer)

    def visualiser(self):
        return self.fichierUrl

    def telecharger(self):
        return self.fichierUrl


# ══════════════════════════════════════════════════════════════════
# HELPER
# ══════════════════════════════════════════════════════════════════

def admin_required(f):
    @wraps(f)
    def dec(*a, **kw):
        if session.get('user_role') != 'admin':
            return redirect(url_for('connexion'))
        return f(*a, **kw)
    return dec


# ══════════════════════════════════════════════════════════════════
# ROUTES PUBLIQUES
# ══════════════════════════════════════════════════════════════════

@app.route('/')
def index():
    produits = Produit.query.filter_by(estActif=True).limit(8).all()
    return render_template('index.html', produits=produits)

@app.route('/catalogue')
def catalogue():
    matiere = request.args.get('matiere', '')
    q = Produit.query.filter_by(estActif=True)
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
        sm = SurMesure(
            nomClient        = data.get('nom', ''),
            numTelephone     = data.get('telephone', ''),
            typeProduit      = data.get('type_produit', ''),
            matiereSouhaitee = data.get('matiere', ''),
            description      = data.get('description', ''),
            photoModele      = data.get('photo', None),
        )
        # Créer aussi CommandeSurMesure liée
        cmd = CommandeSurMesure(
            descriptionSpecifique = data.get('description', ''),
            optionPassageArtisan  = data.get('option_artisan', False)
        )
        sm.envoyerDemande()
        db.session.add(sm)
        db.session.add(cmd)
        db.session.commit()
        return jsonify({'success': True})
    except Exception as e:
        return jsonify({'success': False, 'error': str(e)})

@app.route('/api/session-info')
def session_info():
    return jsonify({
        'logged_in': 'user_id' in session,
        'user_id':   session.get('user_id'),
        'user_nom':  session.get('user_nom'),
        'user_role': session.get('user_role'),
    })


# ══════════════════════════════════════════════════════════════════
# AUTHENTIFICATION
# ══════════════════════════════════════════════════════════════════

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


# ══════════════════════════════════════════════════════════════════
# ROUTES ADMIN
# ══════════════════════════════════════════════════════════════════

@app.route('/admin')
@admin_required
def admin_dashboard():
    stats = TableauDeBord.get_stats()
    produits_recents = Produit.query.filter_by(estActif=True).order_by(Produit.date_ajout.desc()).limit(8).all()
    return render_template('admin/dashboard.html', stats=stats, produits_recents=produits_recents)

@app.route('/admin/produits')
@admin_required
def admin_produits():
    produits = Produit.query.filter_by(estActif=True).order_by(Produit.date_ajout.desc()).all()
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
    tp  = request.form.get('type_produit', 'standard')
    prix = None
    if request.form.get('prix'):
        try: prix = float(request.form.get('prix'))
        except: pass
    responsable.ajouterProduit(
        nom=request.form.get('nom'), matiere=request.form.get('matiere'),
        description=request.form.get('description'), image=img,
        type_produit=tp, prix=prix
    )
    return jsonify({'success': True})

@app.route('/admin/supprimer-produit/<int:id>', methods=['DELETE'])
@admin_required
def supprimer_produit(id):
    responsable = ResponsableBoutique.query.get(session['user_id'])
    success = responsable.supprimerProduit(id)
    return jsonify({'success': success})

@app.route('/admin/promotions', methods=['GET', 'POST'])
@admin_required
def admin_promotions():
    if request.method == 'POST':
        d = request.get_json()
        responsable = ResponsableBoutique.query.get(session['user_id'])
        responsable.appliquerPromotion(d.get('produit_id'), d.get('reduction', 0))
        return jsonify({'success': True})
    produits = Produit.query.filter_by(estActif=True).all()
    return render_template('admin/promotions.html', produits=produits, unread=0)

@app.route('/admin/sur-mesure')
@admin_required
def admin_sur_mesure():
    demandes = SurMesure.query.order_by(SurMesure.date_demande.desc()).all()
    return render_template('admin/sur_mesure.html', demandes=demandes)

@app.route('/admin/supprimer-demande/<int:id>', methods=['DELETE'])
@admin_required
def admin_supprimer_demande(id):
    demande = SurMesure.query.get_or_404(id)
    db.session.delete(demande)
    db.session.commit()
    return jsonify({'success': True})


# ══════════════════════════════════════════════════════════════════
# INITIALISATION BASE DE DONNÉES
# ══════════════════════════════════════════════════════════════════

def init_db():
    db.create_all()

    if not ResponsableBoutique.query.filter_by(role='admin').first():
        db.session.add(ResponsableBoutique(
            nom='Gestionnaire', login='admin@rattanhouse.ma',
            mot_de_passe=generate_password_hash('admin123'), role='admin'
        ))
        db.session.commit()

    if AssistantIA.query.count() == 0:
        db.session.add(AssistantIA())
        db.session.commit()

    if CataloguePDF.query.count() == 0:
        db.session.add(CataloguePDF(fichierUrl='/static/catalogue_rattan_house.pdf', type='Produits', nb_pages=16))
        db.session.add(CataloguePDF(fichierUrl='/static/catalogue_tissus.pdf', type='Tissus', nb_pages=10))
        db.session.commit()

    if Produit.query.count() == 0:
        standards = [
            {'nom':'Salon en rotin exterieur','description':'Salon en rotin ideal pour terrasse.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prixAffiche':17000,'image':'prod_1.jpg'},
            {'nom':'Lampadaire en rotin','description':'Lampadaire en rotin lumiere douce.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':1000,'image':'prod_2.jpg'},
            {'nom':'Salon en rotin arrondi','description':'Design arrondi elegance et confort.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':14500,'image':'prod_3.jpg'},
            {'nom':'Suspension moderne en rotin','description':'Suspension artistique en rotin.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prixAffiche':1500,'image':'prod_4.jpg'},
            {'nom':'Suspension design en rotin','description':'Forme sculpturale originale.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':700,'image':'prod_5.jpg'},
            {'nom':'Applique murale en raphia','description':'Applique murale en raphia naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prixAffiche':150,'image':'prod_6.jpg'},
            {'nom':'Lampadaire en raphia','description':'Lampadaire en raphia.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prixAffiche':250,'image':'prod_7.jpg'},
            {'nom':'Suspension en raphia','description':'Suspension raphia boheme.','caracteristiques':'Matiere: raphia tresse','matiere':'raphia','prixAffiche':900,'image':'prod_8.jpg'},
            {'nom':'Suspension decorative en raphia','description':'Suspension raphia style naturel.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prixAffiche':250,'image':'prod_9.jpg'},
            {'nom':'Lampe de table en raphia','description':'Lampe table raphia minimaliste.','caracteristiques':'Matiere: raphia naturel','matiere':'raphia','prixAffiche':150,'image':'prod_10.jpg'},
            {'nom':'Suspension en fibre naturelle','description':'Suspension fibre naturelle.','caracteristiques':'Matiere: fibre de palmier','matiere':'fibre_palmier','prixAffiche':450,'image':'prod_11.jpg'},
            {'nom':'Tabouret en bois et doum','description':'Tabouret artisanal robuste.','caracteristiques':'Matiere: bois et doum','matiere':'doum','prixAffiche':60,'image':'prod_12.jpg'},
            {'nom':'Set paniers rangement Doum','description':'Ensemble trois paniers doum.','caracteristiques':'Matiere: fibre doum','matiere':'doum','prixAffiche':290,'image':'prod_13.jpg'},
            {'nom':'Main courante en chanvre','description':'Rampe escalier chanvre.','caracteristiques':'Matiere: chanvre','matiere':'corde_chanvre','prixAffiche':150,'image':'prod_14.jpg'},
            {'nom':'Suspension chapeau jonc de mer','description':'Luminaire jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prixAffiche':450,'image':'prod_15.jpg'},
            {'nom':'Suspension ajouree en doum','description':'Luminaire doum tresse.','caracteristiques':'Matiere: doum','matiere':'doum','prixAffiche':240,'image':'prod_16.jpg'},
            {'nom':'Suspension bambou et corde','description':'Lustre bambou et corde.','caracteristiques':'Matiere: bambou et chanvre','matiere':'corde_chanvre','prixAffiche':750,'image':'prod_17.jpg'},
            {'nom':'Suspension Boule Jonc de Mer','description':'Suspension globe jonc de mer.','caracteristiques':'Matiere: jonc de mer','matiere':'jonc_de_mer','prixAffiche':350,'image':'prod_19.jpg'},
            {'nom':'Rouleau cannage en rotin','description':'Cannage qualite superieure.','caracteristiques':'Matiere: moelle de rotin','matiere':'rotin','prixAffiche':400,'image':'prod_20.jpg'},
            {'nom':'Canape Corbeille en Rotin','description':'Canape sculptural rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':8800,'image':'prod_21.jpg'},
            {'nom':'Chaise Paon rotin avec motif','description':'Chaise paon spectaculaire.','caracteristiques':'Matiere: rotin tresse','matiere':'rotin','prixAffiche':8000,'image':'prod_22.jpg'},
            {'nom':'Chaise Paon rotin simple','description':'Chaise paon epuree.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':6800,'image':'prod_23.jpg'},
            {'nom':'Chaise longue vintage rotin','description':'Chaise longue vintage.','caracteristiques':'Matiere: rotin et bambou','matiere':'rotin','prixAffiche':7000,'image':'prod_24.jpg'},
            {'nom':'Decoration murale raphia','description':'Deco murale raphia soleil.','caracteristiques':'Matiere: raphia et perles bois','matiere':'raphia','prixAffiche':180,'image':'prod_25.jpg'},
            {'nom':'Duo plateaux tresses osier','description':'Plateaux ronds osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prixAffiche':90,'image':'prod_26.jpg'},
            {'nom':'Ensemble miroirs raphia rotin','description':'Quatre miroirs raphia rotin.','caracteristiques':'Matiere: raphia et rotin','matiere':'raphia','prixAffiche':770,'image':'prod_27.jpg'},
            {'nom':'Organisation table en osier','description':'Organisateurs table osier.','caracteristiques':'Matiere: osier naturel','matiere':'osier','prixAffiche':90,'image':'prod_28.jpg'},
            {'nom':'Patere murale en osier','description':'Patere murale osier.','caracteristiques':'Matiere: osier/rotin','matiere':'osier','prixAffiche':100,'image':'prod_29.jpg'},
            {'nom':'Rangement rotin console','description':'Meuble rangement rotin.','caracteristiques':'Matiere: rotin et osier','matiere':'rotin','prixAffiche':3400,'image':'prod_32.jpg'},
            {'nom':'Etagere arche en rotin','description':'Etagere arche rotin.','caracteristiques':'Matiere: rotin naturel','matiere':'rotin','prixAffiche':4800,'image':'prod_33.jpg'},
            {'nom':'Serie paniers cannage rotin','description':'Trois paniers cannage rotin.','caracteristiques':'Matiere: cannage rotin','matiere':'rotin','prixAffiche':2100,'image':'prod_34.jpg'},
            {'nom':'Suspension design rotin noir','description':'Suspension rotin noir.','caracteristiques':'Matiere: rotin noir','matiere':'rotin','prixAffiche':700,'image':'prod_35.jpg'},
            {'nom':'Suspension corde jute simple','description':'Suspension jute minimaliste.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','prixAffiche':280,'image':'prod_36.jpg'},
            {'nom':'Suspension corde jute decoree','description':'Suspension jute pompons.','caracteristiques':'Matiere: jute et perles bois','matiere':'corde_chanvre','prixAffiche':600,'image':'prod_37.jpg'},
            {'nom':'Tabouret de bar en rotin','description':'Tabouret bar rotin moderne.','caracteristiques':'Matiere: rotin et metal','matiere':'rotin','prixAffiche':700,'image':'prod_38.jpg'},
        ]
        mesures = [
            {'nom':'Parasol exotique paille naturelle','description':'Parasol paille ambiance tropicale.','caracteristiques':'Matiere: roseau ou paille','matiere':'roseau','image':'prod_18.jpg'},
            {'nom':'Pergola en corde de jute','description':'Pergola jute sur mesure.','caracteristiques':'Matiere: corde de jute','matiere':'corde_chanvre','image':'prod_30.jpg'},
            {'nom':'Pergola brise-vue en chaume','description':'Pergola chaume naturel.','caracteristiques':'Matiere: chaume et bois','matiere':'roseau','image':'prod_31.jpg'},
        ]
        for p in standards: db.session.add(ProduitStandard(**p))
        for p in mesures:    db.session.add(ProduitSurMesure(**p))
        db.session.commit()
        print(f"✓ {len(standards)+len(mesures)} produits inseres")

with app.app_context():
    init_db()

if __name__ == '__main__':
    app.run(debug=False, port=5000)

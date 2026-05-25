from flask import Flask, jsonify, request, send_from_directory
from flask_sqlalchemy import SQLAlchemy
from flask_jwt_extended import (
    JWTManager, create_access_token,
    jwt_required, get_jwt_identity
)
from flask_cors import CORS
from datetime import timedelta
import uuid, math, os
from werkzeug.security import generate_password_hash, check_password_hash
from dotenv import load_dotenv
load_dotenv()
import networkx as nx

app = Flask(__name__)
CORS(app)

app.config["SQLALCHEMY_DATABASE_URI"] = os.getenv("DATABASE_URL", "sqlite:///doacoes.db")
app.config["JWT_SECRET_KEY"] = os.getenv("JWT_SECRET", "dev-secret-change-me")
app.config["JWT_ACCESS_TOKEN_EXPIRES"] = timedelta(hours=8)

db  = SQLAlchemy(app)
jwt = JWTManager(app)

from functools import wraps

# ── HERANÇA DE PERFIS ──
class Doador:
    def cadastrar_item(self, item):
        return True

class Beneficiario:
    def fazer_solicitacao(self, solicitacao):
        return True

class Organizacao:
    def intermediar_doacao(self, doacao):
        return True

class AlgoritmoMatching:
    @staticmethod
    def calcular_distancia(a, b):
        return haversine(a["lat"], a["lng"], b["lat"], b["lng"])

    @staticmethod
    def match(itens, solicitacoes):
        return algoritmo_matching(itens, solicitacoes)

# ── CONTROLE DE PERMISSÃO ──
def role_required(role):
    def wrapper(fn):
        @wraps(fn)
        @jwt_required()
        def decorated(*args, **kwargs):
            usuario = Usuario.query.get(get_jwt_identity())
            if not usuario or usuario.role != role:
                return jsonify({"msg": "Acesso negado"}), 403
            return fn(*args, **kwargs)
        return decorated
    return wrapper


class Usuario(db.Model):
    __tablename__ = "usuario"
    id         = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    nome       = db.Column(db.String(120), nullable=False)
    email      = db.Column(db.String(180), unique=True, nullable=False)
    senha_hash = db.Column(db.String(256), nullable=False)
    role       = db.Column(db.String(20), nullable=False)

    def to_dict(self):
        return {"id": self.id, "nome": self.nome, "email": self.email, "role": self.role}


class ItemDoado(db.Model):
    __tablename__ = "item_doado"
    id        = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    doador_id = db.Column(db.String(36), db.ForeignKey("usuario.id"), nullable=False)
    categoria = db.Column(db.String(60), nullable=False)
    descricao = db.Column(db.Text)
    status    = db.Column(db.String(20), default="disponivel")
    lat       = db.Column(db.Float)
    lng       = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id, "doador_id": self.doador_id,
            "categoria": self.categoria, "descricao": self.descricao,
            "status": self.status, "lat": self.lat, "lng": self.lng
        }


class Solicitacao(db.Model):
    __tablename__ = "solicitacao"
    id              = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    beneficiario_id = db.Column(db.String(36), db.ForeignKey("usuario.id"), nullable=False)
    categoria       = db.Column(db.String(60), nullable=False)
    descricao       = db.Column(db.Text)
    status          = db.Column(db.String(20), default="aberta")
    lat             = db.Column(db.Float)
    lng             = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id, "beneficiario_id": self.beneficiario_id,
            "categoria": self.categoria, "descricao": self.descricao,
            "status": self.status, "lat": self.lat, "lng": self.lng
        }


class Doacao(db.Model):
    __tablename__ = "doacao"
    id             = db.Column(db.String(36), primary_key=True, default=lambda: str(uuid.uuid4()))
    item_id        = db.Column(db.String(36), db.ForeignKey("item_doado.id"), unique=True, nullable=False)
    solicitacao_id = db.Column(db.String(36), db.ForeignKey("solicitacao.id"), unique=True, nullable=False)
    status         = db.Column(db.String(20), default="pendente")
    distancia_km   = db.Column(db.Float)

    def to_dict(self):
        return {
            "id": self.id, "item_id": self.item_id,
            "solicitacao_id": self.solicitacao_id,
            "status": self.status, "distancia_km": self.distancia_km
        }


def haversine(lat1, lng1, lat2, lng2):
    R = 6371.0
    phi1, phi2 = math.radians(lat1), math.radians(lat2)
    dphi    = math.radians(lat2 - lat1)
    dlambda = math.radians(lng2 - lng1)
    a = math.sin(dphi/2)**2 + math.cos(phi1)*math.cos(phi2)*math.sin(dlambda/2)**2
    return R * 2 * math.atan2(math.sqrt(a), math.sqrt(1-a))


def algoritmo_matching(itens, solicitacoes, raio_km=50.0):
    G = nx.Graph()
    for item in itens:
        G.add_node(f"I_{item['id']}", bipartite=0, data=item)
    for sol in solicitacoes:
        G.add_node(f"S_{sol['id']}", bipartite=1, data=sol)
    for item in itens:
        for sol in solicitacoes:
            if item["categoria"].lower() != sol["categoria"].lower():
                continue
            if None in (item.get("lat"), item.get("lng"), sol.get("lat"), sol.get("lng")):
                dist = 0.0
            else:
                dist = haversine(item["lat"], item["lng"], sol["lat"], sol["lng"])
                if dist > raio_km:
                    continue
            G.add_edge(f"I_{item['id']}", f"S_{sol['id']}", weight=-dist)
    matching = nx.max_weight_matching(G, maxcardinality=True)
    resultados = []
    for a, b in matching:
        node_i = a if a.startswith("I_") else b
        node_s = b if b.startswith("S_") else a
        dist   = abs(G[node_i][node_s]["weight"])
        resultados.append({
            "item_id": node_i[2:],
            "solicitacao_id": node_s[2:],
            "distancia_km": round(dist, 2)
        })
    return resultados


# ── SEED: contas de teste criadas automaticamente ──
def seed_contas():
    contas = [
        {"nome": "João Doador",       "email": "doador@teste.com",       "senha": "123456", "role": "doador"},
        {"nome": "Maria Beneficiária","email": "beneficiario@teste.com",  "senha": "123456", "role": "beneficiario"},
        {"nome": "ONG Esperança",     "email": "organizacao@teste.com",   "senha": "123456", "role": "organizacao"},
    ]
    for c in contas:
        if not Usuario.query.filter_by(email=c["email"]).first():
            db.session.add(Usuario(nome=c["nome"], email=c["email"], senha_hash=generate_password_hash(c["senha"]), role=c["role"]))
    db.session.commit()



def validar_coordenadas(lat, lng):
    if lat is None or lng is None:
        return True
    return -90 <= float(lat) <= 90 and -180 <= float(lng) <= 180


# ── ROTAS ──

@app.route("/")
def home():
    return send_from_directory(".", "index.html")


@app.get("/api/contas-teste")
def contas_teste():
    return jsonify([
        {"role": "doador",       "email": "doador@teste.com",      "senha": "123456"},
        {"role": "beneficiario", "email": "beneficiario@teste.com", "senha": "123456"},
        {"role": "organizacao",  "email": "organizacao@teste.com",  "senha": "123456"},
    ])


@app.post("/api/auth/login")
def login():
    data    = request.get_json()
    usuario = Usuario.query.filter_by(email=data.get("email")).first()
    if not usuario or not check_password_hash(usuario.senha_hash, data.get("senha")):
        return jsonify({"msg": "Credenciais inválidas"}), 401
    token = create_access_token(identity=usuario.id)
    return jsonify({"access_token": token, "usuario": usuario.to_dict()})


@app.post("/api/auth/registro")
def registro():
    data = request.get_json()
    if not data.get("nome") or not data.get("email") or not data.get("senha"):
        return jsonify({"msg": "Nome, email e senha são obrigatórios"}), 400
    if Usuario.query.filter_by(email=data["email"]).first():
        return jsonify({"msg": "E-mail já cadastrado"}), 409
    novo = Usuario(nome=data["nome"], email=data["email"],
                   senha_hash=generate_password_hash(data["senha"]), role=data.get("role", "doador"))
    db.session.add(novo)
    db.session.commit()
    return jsonify(novo.to_dict()), 201


@app.get("/api/itens")
@jwt_required()
def listar_itens():
    categoria = request.args.get("categoria")
    lat  = request.args.get("lat", type=float)
    lng  = request.args.get("lng", type=float)
    raio = request.args.get("raio", 50.0, type=float)
    query = ItemDoado.query.filter_by(status="disponivel")
    if categoria:
        query = query.filter(ItemDoado.categoria.ilike(f"%{categoria}%"))
    itens = query.all()
    if lat and lng:
        itens = [i for i in itens if i.lat and i.lng and haversine(lat, lng, i.lat, i.lng) <= raio]
    return jsonify([i.to_dict() for i in itens])


@app.post("/api/itens")
@jwt_required()
def criar_item():
    data    = request.get_json()
    user_id = get_jwt_identity()
    if not data.get("categoria"):
        return jsonify({"msg": "Categoria é obrigatória"}), 400
    if not validar_coordenadas(data.get("lat"), data.get("lng")):
        return jsonify({"msg": "Coordenadas inválidas"}), 400
    if not validar_coordenadas(data.get("lat"), data.get("lng")):
        return jsonify({"msg": "Coordenadas inválidas"}), 400
    item = ItemDoado(
        doador_id=user_id,
        categoria=data["categoria"],
        descricao=data.get("descricao", ""),
        lat=data.get("lat"),
        lng=data.get("lng")
    )
    db.session.add(item)
    db.session.commit()
    return jsonify(item.to_dict()), 201


@app.get("/api/solicitacoes")
@jwt_required()
def listar_solicitacoes():
    sols = Solicitacao.query.filter_by(status="aberta").all()
    return jsonify([s.to_dict() for s in sols])


@app.post("/api/solicitacoes")
@jwt_required()
def criar_solicitacao():
    data    = request.get_json()
    user_id = get_jwt_identity()
    if not data.get("categoria"):
        return jsonify({"msg": "Categoria é obrigatória"}), 400
    sol = Solicitacao(
        beneficiario_id=user_id,
        categoria=data["categoria"],
        descricao=data.get("descricao", ""),
        lat=data.get("lat"),
        lng=data.get("lng")
    )
    db.session.add(sol)
    db.session.commit()
    return jsonify(sol.to_dict()), 201


@app.post("/api/matching/executar")
@jwt_required()
def executar_matching():
    raio  = request.args.get("raio", 50.0, type=float)
    itens = [i.to_dict() for i in ItemDoado.query.filter_by(status="disponivel").all()]
    sols  = [s.to_dict() for s in Solicitacao.query.filter_by(status="aberta").all()]
    pares = algoritmo_matching(itens, sols, raio_km=raio)
    novas = []
    for par in pares:
        item = db.session.get(ItemDoado, par["item_id"])
        sol  = db.session.get(Solicitacao, par["solicitacao_id"])
        if not item or not sol:
            continue
        existente = Doacao.query.filter_by(item_id=par["item_id"], solicitacao_id=par["solicitacao_id"]).first()
        if existente:
            continue
        item.status = "reservado"
        sol.status  = "em_atendimento"
        doacao = Doacao(item_id=par["item_id"], solicitacao_id=par["solicitacao_id"],
                        distancia_km=par["distancia_km"])
        db.session.add(doacao)
        db.session.flush()
        novas.append(doacao.to_dict())
    db.session.commit()
    return jsonify({"matches_gerados": len(novas), "doacoes": novas})


@app.get("/api/relatorios/impacto")
@jwt_required()
def relatorio_impacto():
    total_itens   = ItemDoado.query.count()
    total_sols    = Solicitacao.query.count()
    total_doacoes = Doacao.query.count()
    entregues     = Doacao.query.filter_by(status="entregue").count()
    pendentes     = Doacao.query.filter_by(status="pendente").count()
    return jsonify({
        "total_itens_cadastrados": total_itens,
        "total_solicitacoes":      total_sols,
        "total_doacoes_geradas":   total_doacoes,
        "doacoes_entregues":       entregues,
        "doacoes_pendentes":       pendentes,
        "taxa_atendimento_pct":    round(entregues / total_sols * 100, 1) if total_sols else 0
    })




@app.delete("/api/itens/<item_id>")
@jwt_required()
def remover_item(item_id):
    user_id = get_jwt_identity()
    item = db.session.get(ItemDoado, item_id)
    if not item:
        return jsonify({"msg": "Item não encontrado"}), 404
    if item.doador_id != user_id:
        return jsonify({"msg": "Sem permissão"}), 403
    db.session.delete(item)
    db.session.commit()
    return jsonify({"msg": "Item removido com sucesso"})


@app.get("/api/doacoes")
@jwt_required()
def listar_doacoes():
    doacoes = Doacao.query.all()
    resultado = []
    for d in doacoes:
        item = db.session.get(ItemDoado, d.item_id)
        solicitacao = db.session.get(Solicitacao, d.solicitacao_id)
        doador = db.session.get(Usuario, item.doador_id) if item else None
        beneficiario = db.session.get(Usuario, solicitacao.beneficiario_id) if solicitacao else None

        resultado.append({
            "id": d.id,
            "status": d.status,
            "distancia_km": d.distancia_km,
            "item": item.to_dict() if item else None,
            "doador": doador.to_dict() if doador else None,
            "beneficiario": beneficiario.to_dict() if beneficiario else None
        })
    return jsonify(resultado)


@app.put("/api/doacoes/<doacao_id>/status")
@jwt_required()
def atualizar_status_doacao(doacao_id):
    data = request.get_json()
    novo_status = data.get("status")

    status_validos = ["pendente", "em_transporte", "entregue", "cancelada"]

    if novo_status not in status_validos:
        return jsonify({"msg": "Status inválido"}), 400

    doacao = db.session.get(Doacao, doacao_id)

    if not doacao:
        return jsonify({"msg": "Doação não encontrada"}), 404

    doacao.status = novo_status

    if novo_status == "entregue":
        item = db.session.get(ItemDoado, doacao.item_id)
        solicitacao = db.session.get(Solicitacao, doacao.solicitacao_id)

        if item:
            item.status = "doado"

        if solicitacao:
            solicitacao.status = "finalizada"

    db.session.commit()

    return jsonify({"msg": "Status atualizado", "doacao": doacao.to_dict()})


@app.errorhandler(Exception)
def handle_error(e):
    return jsonify({"erro": str(e)}), 500

@app.get("/api/me")
@jwt_required()
def me():
    user_id = get_jwt_identity()
    user = db.session.get(Usuario, user_id)
    return jsonify(user.to_dict() if user else {})



@app.get("/api/dashboard/doador")
@role_required("doador")
def dashboard_doador():
    uid = get_jwt_identity()
    itens = ItemDoado.query.filter_by(doador_id=uid).all()
    return jsonify({"tipo":"doador","itens":[i.to_dict() for i in itens]})

@app.get("/api/dashboard/beneficiario")
@role_required("beneficiario")
def dashboard_beneficiario():
    uid = get_jwt_identity()
    solicitacoes = Solicitacao.query.filter_by(beneficiario_id=uid).all()
    return jsonify({"tipo":"beneficiario","solicitacoes":[s.to_dict() for s in solicitacoes]})

@app.get("/api/dashboard/organizacao")
@role_required("organizacao")
def dashboard_organizacao():
    doacoes = Doacao.query.all()
    return jsonify({"tipo":"organizacao","doacoes":[d.to_dict() for d in doacoes]})

@app.post("/api/doacoes/<doacao_id>/aprovar")
@role_required("organizacao")
def aprovar_doacao(doacao_id):
    doacao = Doacao.query.get_or_404(doacao_id)
    doacao.status = "aprovado"
    db.session.commit()
    return jsonify(doacao.to_dict())


if __name__ == "__main__":
    with app.app_context():
        db.create_all()
        seed_contas()
    app.run(debug=True, port=5000)

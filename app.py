from flask import Flask, render_template, redirect, url_for, session, g
import sqlite_utils
import uuid
import os

# 1. Inicialización de la aplicación y Clave Secreta
app = Flask(__name__)
# Usa una clave secreta fuerte aquí, como se indicó en el Paso 18
app.secret_key = 'MiEquipoF1EsMejorQueElDeFerrariEn2027ConPocoDinero!' 

# 2. Configuración de la Base de Datos (SQLite)
DATABASE_FILE = 'f1_gestion.db'

# 3. Función para obtener la conexión a la DB
def get_db():
    if 'db' not in g:
        g.db = sqlite_utils.Database(DATABASE_FILE)
    return g.db

# 4. Función que se ejecuta DESPUÉS de cada solicitud para cerrar la DB
@app.teardown_appcontext
def close_db(e=None):
    db = g.pop('db', None)
    if db is not None:
        db.close()

# 5. Lógica de Pre-petición: Gestiona el ID de Sesión (jugador)
@app.before_request
def check_player_id():
    # 5.1. Asignar ID de Sesión
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())

    db = get_db()
    player_id = session['player_id']

    # 5.2. Asegurar que la tabla 'jugadores' existe
    if not db["jugadores"].exists():
        db["jugadores"].create({"id": str, "dia": int}, pk="id")

    # 5.3. Insertar/Ignorar jugador (para garantizar que existe)
    db["jugadores"].insert({
        "id": player_id,
        "dia": 1
    }, pk="id", ignore=True)

    # 5.4. Asegurar que la tabla 'componentes' existe y está inicializada
    if not db["componentes"].exists():
        db["componentes"].create({
            "jugador_id": str,
            "nombre": str,
            "nivel_rd": int,
            "coste": int,
            "rendimiento_base": float
        }, pk=("jugador_id", "nombre")) # Clave primaria compuesta por Jugador + Nombre

    # 5.5. Inicializar componentes solo si el jugador no tiene ninguno aún
    if list(db["componentes"].rows_where("jugador_id = ?", params=[player_id])) == []:
         # Componentes base de F1
        componentes_iniciales = [
            {"jugador_id": player_id, "nombre": "Motor", "nivel_rd": 1, "coste": 500, "rendimiento_base": 1.0},
            {"jugador_id": player_id, "nombre": "Alerón Delantero", "nivel_rd": 1, "coste": 200, "rendimiento_base": 0.8},
            {"jugador_id": player_id, "nombre": "Chasis", "nivel_rd": 1, "coste": 700, "rendimiento_base": 1.5},
        ]
        # insert_all asegura que se añaden los tres componentes de una vez
        db["componentes"].insert_all(componentes_iniciales, pk=("jugador_id", "nombre"), replace=True)


# 6. Ruta principal: Muestra el estado del jugador actual
@app.route('/')
def index():
    db = get_db()
    player_id = session['player_id']

    player_state = db["jugadores"].get(player_id) 

    # Cargar los componentes asociados a ESTE jugador
    componentes = list(db["componentes"].rows_where("jugador_id = ?", params=[player_id]))

    # Pasamos el día y los componentes a la plantilla HTML
    return render_template('index.html', dia_actual=player_state['dia'], componentes=componentes)


# 7. Ruta para avanzar el tiempo (y guardar)
@app.route('/avanzar')
def avanzar_dia():
    db = get_db()
    player_id = session['player_id']

    # Cargamos el estado, incrementamos el día y guardamos
    player_state = db["jugadores"].get(player_id)
    nuevo_dia = player_state['dia'] + 1

    # Guardamos el nuevo día en la base de datos (clave: player_id)
    db["jugadores"].update(player_id, {"dia": nuevo_dia})

    # Redirigimos al usuario de vuelta a la página principal (/)
    return redirect(url_for('index'))

# Esta línea es solo para pruebas locales (Codespaces)
if __name__ == '__main__':
    app.run(debug=True)
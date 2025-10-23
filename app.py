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
    # Si el jugador no tiene un ID de sesión, se lo asignamos.
    if 'player_id' not in session:
        session['player_id'] = str(uuid.uuid4())

    db = get_db()

    # 1. Aseguramos que la tabla 'jugadores' existe
    if not db["jugadores"].exists():
        db["jugadores"].create({"id": str, "dia": int}, pk="id")

    # 2. Intentamos insertar el jugador en Día 1.
    # Si el jugador ya existe (por su ID), la inserción es IGNORADA.
    db["jugadores"].insert({
        "id": session['player_id'],
        "dia": 1
    }, pk="id", ignore=True)


# 6. Ruta principal: Muestra el estado del jugador actual
@app.route('/')
def index():
    db = get_db()
    # Usamos get() aquí, pues la función before_request garantiza que el ID ya existe
    player_state = db["jugadores"].get(session['player_id']) 

    # Pasamos el día individual del jugador a la plantilla HTML
    return render_template('index.html', dia_actual=player_state['dia'])


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
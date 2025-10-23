from flask import Flask, render_template, redirect, url_for, session, g, flash, request
from datetime import datetime, timedelta 
import sqlite_utils
from sqlite_utils.db import NotFoundError 
import uuid
import time 
import os

# 1. Inicialización de la aplicación y Clave Secreta
app = Flask(__name__)
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

# --- CONSTANTES GLOBALES DE TIEMPO ---
START_DATE = datetime(2025, 12, 1, 0, 0, 0) # 1 de Diciembre de 2025, 00:00:00
SEASON_START_DATE = datetime(2026, 4, 1, 0, 0, 0) # 1 de Abril de 2026
# ----------------------------------------------------


# 6. Ruta principal: Muestra el estado del jugador actual con lógica RT
@app.route('/')
def index():
    db = get_db()
    player_id = session.get('player_id')
    player_state = None 

    # Lógica de seguridad para evitar el error 500
    if player_id and db["jugadores"].exists():
        try:
            player_state = db["jugadores"].get(player_id)
        except NotFoundError:
            session.pop('player_id', None) 
            player_state = None 

    # CLAVE: Si no hay jugador VÁLIDO (o la sesión fue limpiada), redirige a Bienvenida
    if not player_state:
        return redirect(url_for('bienvenida'))

    # --- Lógica de cálculo de tiempo REAL-TIME (4x) ---
    real_time_elapsed = time.time() - player_state['start_time_rt']
    game_time_elapsed = real_time_elapsed * 4 
    current_game_date = START_DATE + timedelta(seconds=game_time_elapsed)
    game_day_number = (current_game_date - START_DATE).days + 1
    
    # Actualizar el 'dia' en la base de datos (clave para proyectos y carrera)
    if player_state['dia'] != game_day_number:
        db["jugadores"].update(player_id, {"dia": game_day_number})
        player_state['dia'] = game_day_number 
        # ELIMINADO: db.commit() - No es necesario en sqlite-utils
        
    # --- Lógica de Hitos Importantes (TAREA 5) ---
    days_to_season = max(0, (SEASON_START_DATE - current_game_date).days)
    proxima_carrera = "Inicio de Temporada"
    fecha_proxima_carrera = SEASON_START_DATE.strftime("%d %b %Y")

    if current_game_date >= SEASON_START_DATE:
        days_since_season_start = (current_game_date - SEASON_START_DATE).days
        races_completed = days_since_season_start // 14
        next_race_date = SEASON_START_DATE + timedelta(days=(races_completed + 1) * 14)
        proxima_carrera = "Carrera (TBD)" 
        fecha_proxima_carrera = next_race_date.strftime("%d %b %Y")
    
    # ---------------------------------------------

    componentes = list(db["componentes"].rows_where("jugador_id = ?", [player_id]))
    
    # Manejar la posible inexistencia de la tabla 'proyectos'
    # Nota: Asegúrate de que 'proyectos' se crea antes de que un proyecto se inicie, si no existe.
    proyectos = list(db["proyectos"].rows_where("jugador_id = ?", [player_id])) if db.get("proyectos", {}).exists() else []


    # Renderizar la página principal con los nuevos datos de tiempo.
    return render_template('index.html', 
                            player_state=player_state,
                            componentes=componentes, 
                            proyectos=proyectos,
                            start_timestamp=player_state['start_time_rt'], 
                            current_game_date=current_game_date.strftime("%d %B %Y"),
                            current_game_time=current_game_date.strftime("%H:%M:%S"),
                            game_day_number=game_day_number,
                            days_to_season=days_to_season,
                            proxima_carrera=proxima_carrera,
                            fecha_proxima_carrera=fecha_proxima_carrera,
                            escuderia_nombre="Phoenix Racing")


# 8. Ruta para iniciar un proyecto de I+D
@app.route('/iniciar_rd/<nombre_componente>')
def iniciar_rd(nombre_componente):
    db = get_db()
    player_id = session['player_id']

    player_state = db["jugadores"].get(player_id)

    # 1. Comprobación de proyecto activo
    if player_state['proyecto_activo'] is not None:
        return redirect(url_for('index')) 

    # 2. Obtener datos del componente
    componente = db["componentes"].get((player_id, nombre_componente))
    coste_rd = componente['coste_mejora'] * componente['nivel_rd'] 

    # 3. Comprobación de fondos
    if player_state['dinero'] >= coste_rd:
        # 4. Iniciar el proyecto
        dias_proyecto = 5
        dia_finalizacion = player_state['dia'] + dias_proyecto

        db["jugadores"].update(player_id, {
            "dinero": player_state['dinero'] - coste_rd,
            "proyecto_activo": nombre_componente,
            "dia_finalizacion_rd": dia_finalizacion 
        })

    return redirect(url_for('index'))

# 9. Ruta para simular una carrera
@app.route('/carrera')
def carrera():
    db = get_db()
    player_id = session['player_id']
    player_state = db["jugadores"].get(player_id)

    # 1. Comprobación: Solo si es el Día 10
    if player_state['dia'] != 10:
        flash("La carrera solo puede simularse el Día 10.")
        return redirect(url_for('index'))

    # 2. Cargar el Rendimiento del Jugador
    componentes = list(db["componentes"].rows_where("jugador_id = ?", [player_id]))
    rendimiento_total = 0

    for comp in componentes:
        rendimiento_total += comp['rendimiento_base'] + (comp['nivel_rd'] * 0.1)

    # 3. Simulación del Resultado (Ejemplo Simple)
    factor_mejora = rendimiento_total / len(componentes)

    posicion_simulada = max(1, round(15 - (factor_mejora * 2))) 

    # 4. Asignar Recompensa y Guardar Resultados
    premio_dinero = 0

    if posicion_simulada <= 5:
        premio_dinero = 5000 + (6 - posicion_simulada) * 1000 
    elif posicion_simulada <= 10:
        premio_dinero = 1000

    # 5. Actualizar estado del jugador (solo dinero)
    db["jugadores"].update(player_id, {
        "dinero": player_state['dinero'] + premio_dinero,
    })

    # 6. Mostrar resultado de la carrera
    return render_template('carrera.html', 
                            posicion=posicion_simulada, 
                            premio=premio_dinero, 
                            rendimiento=round(factor_mejora, 2),
                            player_state=player_state, 
                            dia_actual=player_state['dia']) 

# 9. Nueva ruta de Bienvenida y Configuración
@app.route('/bienvenida', methods=['GET', 'POST'])
def bienvenida():
    db = get_db()
    player_id = session.get('player_id')

    # 1. Asegurar que la tabla 'jugadores' existe ANTES de hacer .get()
    if not db["jugadores"].exists():
        db["jugadores"].create({
            "id": str, 
            "dia": int,
            "dinero": int,
            "director_name": str, 
            "start_time_rt": float, 
            "proyecto_activo": str, 
            "dia_finalizacion_rd": int
        }, pk="id")
        
    # Si ya hay un jugador VÁLIDO, redirigir a index
    try:
        if player_id and db["jugadores"].get(player_id):
            return redirect(url_for('index'))
    except NotFoundError:
        # Si el cookie es viejo, lo ignoramos y procedemos a crear uno nuevo
        session.pop('player_id', None)

    if request.method == 'POST':
        director_name = request.form.get('director_name')
        if not director_name:
            flash("Por favor, introduce tu nombre de director.")
            return render_template('bienvenida.html', escuderia_nombre="Phoenix Racing", fecha_inicio="1 de Diciembre de 2025")

        # Crear un nuevo ID de jugador
        new_player_id = str(uuid.uuid4()) 
        session['player_id'] = new_player_id

        # 2. Crear el jugador en la BD (con todos los nuevos campos)
        db["jugadores"].insert({
            "id": new_player_id,
            "dinero": 100000,
            "dia": 1,
            "director_name": director_name,
            "start_time_rt": time.time(), 
            "proyecto_activo": None, 
            "dia_finalizacion_rd": None 
        }, pk="id")

        # 3. Inicializar los componentes 
        db["componentes"].create({
            "jugador_id": str,
            "nombre": str,
            "nivel_rd": int,
            "coste_mejora": int,
            "rendimiento_base": float
        }, pk=("jugador_id", "nombre"), ignore=True)
        
        db["componentes"].insert_all([
            {"jugador_id": new_player_id, "nombre": "Chasis", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Motor", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Alerón Delantero", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Alerón Trasero", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
        ], replace=True)

        # ELIMINADO: db.commit() - No es necesario y causaba el error 500

        flash(f"¡Bienvenido, Director {director_name}! ¡Es hora de relanzar Phoenix Racing!")
        return redirect(url_for('index'))

    # GET request: Mostrar la página de bienvenida
    return render_template('bienvenida.html', 
                            escuderia_nombre="Phoenix Racing",
                            fecha_inicio="1 de Diciembre de 2025")

# 10. Nueva ruta para resetear la sesión (Solo borra la sesión)
@app.route('/reset')
def reset_session():
    from flask import session, flash, redirect, url_for 
    
    session.pop('player_id', None)
    
    flash("Sesión de jugador reseteada. Comienza un nuevo juego.")
    return redirect(url_for('bienvenida')) 

if __name__ == '__main__':
    app.run(debug=True)

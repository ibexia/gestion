from flask import Flask, render_template, redirect, url_for, session, g
import sqlite_utils
import uuid
import time # Necesario para la lógica de tiempo real (Tarea 3)
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
        db["jugadores"].create({
            "id": str, 
            "dia": int,
            "dinero": int, # <--- ¡Añadir!
            "proyecto_activo": str, # <--- ¡Añadir!
            "dia_finalizacion_rd": int # <--- ¡Añadir!
        }, pk="id")

    # 5.3. Insertar/Ignorar jugador (para garantizar que existe y darle dinero inicial)
    db["jugadores"].insert({
        "id": player_id,
        "dia": 1,
        "dinero": 10000, # <-- DINERO INICIAL
        "proyecto_activo": None, # <-- Proyecto en marcha
        "dia_finalizacion_rd": None # <-- Día en que termina el proyecto
    }, pk="id", ignore=True, alter=True) # <-- ¡ALTER=TRUE AÑADIDO AQUÍ!

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
    if list(db["componentes"].rows_where("jugador_id = ?", [player_id])) == []:
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

    if not player_id or not db["jugadores"].get(player_id):
        # Si no hay jugador, redirigir a la pantalla de bienvenida/configuración
        return redirect(url_for('bienvenida'))

    player_state = db["jugadores"].get(player_id) 

    # --- Lógica de cálculo de tiempo (Se usará en Tarea 3 y 4) ---
    dia_actual = player_state['dia']

    componentes = list(db["componentes"].rows_where("jugador_id = ?", [player_id]))
    proyectos = list(db["proyectos"].rows_where("jugador_id = ?", [player_id]))

    # Renderizar la página principal con el estado del jugador y datos.
    return render_template('index.html', 
                           player_state=player_state, 
                           dia_actual=dia_actual,
                           componentes=componentes, 
                           proyectos=proyectos,
                           escuderia_nombre="Phoenix Racing") # <-- Escudería fija

# 7. Ruta para avanzar el tiempo (y guardar)
@app.route('/avanzar')
def avanzar_dia():
    db = get_db()
    player_id = session['player_id']

    # 1. Obtener estado actual
    player_state = db["jugadores"].get(player_id)
    nuevo_dia = player_state['dia'] + 1

    # 2. Comprobar si hay un proyecto activo y si ha finalizado
    proyecto_activo = player_state.get('proyecto_activo') # Usa .get() para evitar KeyError
    dia_finalizacion = player_state.get('dia_finalizacion_rd')

    if proyecto_activo and dia_finalizacion is not None and nuevo_dia >= dia_finalizacion:
        # ¡PROYECTO FINALIZADO!

        # 2.1. Subir nivel del componente
        componente = db["componentes"].get((player_id, proyecto_activo))
        db["componentes"].update((player_id, proyecto_activo), {
            "nivel_rd": componente['nivel_rd'] + 1,
        })

        # 2.2. Limpiar variables del proyecto
        db["jugadores"].update(player_id, {
            "dia": nuevo_dia,
            "proyecto_activo": None,
            "dia_finalizacion_rd": None
        })
    else:
        # 3. Solo avanzamos el día (el proyecto sigue en marcha o no hay proyecto)
        db["jugadores"].update(player_id, {"dia": nuevo_dia})

    return redirect(url_for('index'))

# 8. Ruta para iniciar un proyecto de I+D
@app.route('/iniciar_rd/<nombre_componente>')
def iniciar_rd(nombre_componente):
    db = get_db()
    player_id = session['player_id']

    player_state = db["jugadores"].get(player_id)

    # 1. Comprobación de proyecto activo
    if player_state['proyecto_activo'] is not None:
        # Ya hay un proyecto en marcha
        return redirect(url_for('index')) 

    # 2. Obtener datos del componente
    componente = db["componentes"].get((player_id, nombre_componente))
    coste_rd = componente['coste'] * componente['nivel_rd'] # Coste aumenta con el nivel

    # 3. Comprobación de fondos
    if player_state['dinero'] >= coste_rd:
        # 4. Iniciar el proyecto: se establece el componente y se calcula la fecha de finalización
        # Suponemos 5 días para un proyecto, luego se ajustará
        dias_proyecto = 5
        dia_finalizacion = player_state['dia'] + dias_proyecto

        db["jugadores"].update(player_id, {
            "dinero": player_state['dinero'] - coste_rd,
            "proyecto_activo": nombre_componente,
            "dia_finalizacion_rd": dia_finalizacion # Guardamos el día en que terminará
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
        # Fórmula simple: Rendimiento Base + (Nivel * 0.1)
        rendimiento_total += comp['rendimiento_base'] + (comp['nivel_rd'] * 0.1)

    # 3. Simulación del Resultado (Ejemplo Simple)
    # El rendimiento base es 100. Los componentes lo mejoran.

    # Rendimiento Total / Número de Componentes (para sacar un promedio de mejora)
    factor_mejora = rendimiento_total / len(componentes)

    # El resultado se basa en el rendimiento total, donde un resultado más bajo es mejor (posición)
    # Una simulación simple: Posición inicial 15 - (Factor de Mejora * 2)
    posicion_simulada = max(1, round(15 - (factor_mejora * 2))) 

    # 4. Asignar Recompensa y Guardar Resultados
    premio_dinero = 0

    if posicion_simulada <= 5:
        premio_dinero = 5000 + (6 - posicion_simulada) * 1000 # Más dinero si queda mejor
    elif posicion_simulada <= 10:
        premio_dinero = 1000

    # 5. Actualizar estado del jugador (dinero, y avanzar al siguiente día/fase)
    db["jugadores"].update(player_id, {
        "dinero": player_state['dinero'] + premio_dinero,
        "dia": player_state['dia'] + 1 # <--- ¡Esto es el problema! Pasa del día 10 al 11.
    })

    # 6. Mostrar resultado de la carrera
    return render_template('carrera.html', 
                        posicion=posicion_simulada, 
                        premio=premio_dinero, 
                        rendimiento=round(factor_mejora, 2),
                        player_state=player_state, # <--- ¡CLAVE! Pasar el diccionario completo
                        dia_actual=player_state['dia']) # <--- Y el día actual por si la plantilla lo necesita
# Esta línea es solo para pruebas locales (Codespaces)

# 9. Nueva ruta de Bienvenida y Configuración
@app.route('/bienvenida', methods=['GET', 'POST'])
def bienvenida():
    db = get_db()
    player_id = session.get('player_id')

    # Si ya hay un jugador, redirigir a index
    if player_id and db["jugadores"].get(player_id):
        return redirect(url_for('index'))

    if request.method == 'POST':
        director_name = request.form.get('director_name')
        if not director_name:
            flash("Por favor, introduce tu nombre de director.")
            return render_template('bienvenida.html', escuderia_nombre="Phoenix Racing", fecha_inicio="1 de Diciembre de 2025")

        # Crear un nuevo ID de jugador
        new_player_id = str(uuid.uuid4()) 
        session['player_id'] = new_player_id

        # 1. Crear el jugador en la BD (incluyendo director_name y start_time_rt para el futuro)
        db["jugadores"].insert({
            "id": new_player_id,
            "dinero": 100000,
            "dia": 1,
            "director_name": director_name, # <-- Nuevo campo (Tarea 1)
            "start_time_rt": time.time() # Hora de inicio real (Tarea 3)
        }, pk="id")

        # 2. Inicializar los componentes (CÓDIGO DEL PASO 37)
        db["componentes"].insert_all([
            {"jugador_id": new_player_id, "nombre": "Chasis", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Motor", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Alerón Delantero", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
            {"jugador_id": new_player_id, "nombre": "Alerón Trasero", "nivel_rd": 1, "rendimiento_base": 1.5, "coste_mejora": 10000},
        ])

        db.commit()

        flash(f"¡Bienvenido, Director {director_name}! ¡Es hora de relanzar Phoenix Racing!")
        return redirect(url_for('index'))

    # GET request: Mostrar la página de bienvenida
    return render_template('bienvenida.html', 
                           escuderia_nombre="Phoenix Racing",
                           fecha_inicio="1 de Diciembre de 2025")

# 10. Nueva ruta para resetear la sesión
@app.route('/reset')
def reset_session():
    from flask import session, flash, redirect, url_for # Asegúrate de importar esto si no está al inicio
    session.pop('player_id', None)
    flash("Sesión de jugador reseteada. Comienza un nuevo juego.")
    return redirect(url_for('bienvenida'))                           


if __name__ == '__main__':
    app.run(debug=True)
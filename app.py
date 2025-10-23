from flask import Flask, render_template, redirect, url_for

# 1. Inicialización de la aplicación
app = Flask(__name__)

# 2. Variable global para el estado del juego (El tiempo)
# Usaremos una lista para que Python pueda modificar la variable global
ESTADO = {'dia': 1} 

# 3. Ruta principal: Muestra el estado actual
@app.route('/')
def index():
    # Render_template busca index.html en la carpeta 'templates'
    return render_template('index.html', dia_actual=ESTADO['dia'])

# 4. Ruta para avanzar el tiempo
@app.route('/avanzar')
def avanzar_dia():
    # Aumentamos el día en 1
    ESTADO['dia'] += 1
    # Redirigimos al usuario de vuelta a la página principal (/)
    return redirect(url_for('index'))

# Esta línea es para ejecutar la aplicación localmente (en Codespaces)
if __name__ == '__main__':
    app.run(debug=True)
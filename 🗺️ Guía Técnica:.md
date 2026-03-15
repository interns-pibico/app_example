### 🗺️ Guía Técnica:
 Proyecto AsturiasMapServidor: cristinaserver | Base de Datos: asturiasmap
    Este documento resume todos los comandos, configuraciones y flujos de trabajo implementados para el sistema de mapas 3D y actualización automática de datos de Asturias.
 ## 🗄️ 1. Infraestructura de Base de Datos (PostgreSQL + PostGIS)
    La base de datos almacena puntos de interés (POIs) con capacidades geográficas.
 #### Comandos de Administración (psql)
 Comando                        Función
 sudo -u postgres psql          * Acceso root a la consola de Postgres.
 CREATE DATABASE asturiasmap;   * Creación de la base de datos principal.
 CREATE EXTENSION postgis;      * Habilita funciones espaciales (imprescindible).
 \dt                            *Lista todas las tablas de la base de datos.
 
 #### Mantenimiento de Datos
 1. Limpiar espacios en blanco:
     UPDATE puntos_interes SET tipo = TRIM(tipo);
 2. Asegurar integridad (Evitar duplicados):
    ALTER TABLE puntos_interes ADD CONSTRAINT unique_osm_id UNIQUE (osm_id);
 3. Añadir columna de tiempo:
    ALTER TABLE puntos_interes ADD COLUMN ultima_actualizacion TIMESTAMP;
 4. Optimizar búsquedas geográficas (Índice GIST):
    CREATE INDEX idx_puntos_geom ON puntos_interes USING GIST (geom);
 
 ## 🐍 2. Entorno de Desarrollo (Python)
    Utilizamos un entorno virtual para evitar conflictos con otras aplicaciones del servidor.
    Configuración del EntornoBash
 #### Crear y activar entorno virtual
    python3 -m venv venv
    source venv/bin/activate

 #### Instalación de librerías necesarias
    pip install fastapi uvicorn sqlalchemy psycopg2-binary requests python-dotenv

 ### Variables de Entorno (.env)
    El archivo .env debe estar en la raíz para proteger las credenciales:
        DB_NAME=asturiasmap
        DB_USER=tu_usuario
        DB_PASS=tu_contraseña
        DB_HOST=localhost
        DB_PORT=5432

## 🚀 3. Ejecución del SistemaBackend (FastAPI)
#### Para poner en marcha la API que alimenta el mapa:
    uvicorn app.main:app --host 0.0.0.0 --port 8000 --reload
#### Actualización Manual de DatosPara forzar una descarga de datos desde OpenStreetMap:
    ./venv/bin/python3 update_osm_asturias.py

## 🤖 4. Automatización (Tareas Programadas)
    Configuración para que el servidor se actualice solo sin intervención humana.
#### Edición del Crontab (Linux)
    crontab -e
#### Línea de Producción (Ejecución Domingos 5:00 AM)
    0 5 * * 0 /home/erpnext/.services/app_example/venv/bin/python3 /home/erpnext/.services/app_example/update_osm_asturias.py >> /home/erpnext/.services/app_example/asturias_update.log 2>&1
#### Gestión de Logs (Registros)
##### Ver progreso actual: 
        tail -f asturias_update.log
##### Ver últimos resultados:
        tail -n 50 asturias_update.log
##### Vaciar log: 
        true > asturias_update.log

### 🛠️ 5. Flujo de Datos (Arquitectura)
1. Overpass API: Fuente externa de datos de OpenStreetMap.
2. update_osm_asturias.py: Script que filtra, limpia y formatea los datos.
3. PostgreSQL/PostGIS: Almacén persistente y espacial.
4. FastAPI (gijon_api.py): Expone los datos mediante endpoints JSON.
5. Frontend (JS/Mapbox): Renderiza los puntos en el mapa 3D.
**Nota: Mantén siempre una copia del archivo .env fuera del control de versiones (Git) para asegurar la privacidad de tu base de datos.**



******************************************************************************************************************************************


# 🆘 Manual de Recuperación: "CristinaServer Reboot"
    Si el servidor se reinicia o la web deja de cargar, sigue estos pasos en orden para volver a la normalidad en menos de 2 minutos.

## 1. Comprobar el estado de la Base de Datos
    A veces el servicio de Postgres no arranca solo.

    * Comprobar: 
        sudo systemctl status postgresql

    * Si está apagado (Inactivo): 
        sudo systemctl start postgresql

## 2. Levantar el Backend (FastAPI)
    Como no lo tenemos configurado como servicio del sistema todavía, hay que lanzarlo manualmente desde tu carpeta de proyecto.


#### Ir a la carpeta del proyecto
        cd /home/erpnext/.services/app_example/

#### Activar el entorno virtual
        source venv/bin/activate

#### Lanzar FastAPI en segundo plano (usando nohup para que no se cierre al salir)
nohup uvicorn app.main:app --host 0.0.0.0 --port 8000 > fastapi.log 2>&1 &
**Tip: El & al final y el nohup hacen que la API siga funcionando aunque cierres la ventana de la terminal.**

## 3. Verificar la Tarea Programada (Cron)
    El servicio de cron suele ser muy robusto, pero no está de más confirmar que está "vivo".

    *Comprobar: 
        sudo systemctl status cron

    *Ver tus tareas: 
        crontab -l (Si ves la línea de Asturias al final, todo está bien).

## 🔍 "Checklist" de Errores Comunes
**Error: "Port 8000 already in use".**
    Esto pasa si intentas lanzar FastAPI y ya hay uno funcionando.

    *Solución: Mata el proceso antiguo.
        fuser -k 8000/tcp
    *Luego vuelve a lanzar el comando de uvicorn.

**Error: "Ident authentication failed for user...".**
    Suele pasar si Postgres ha cambiado su configuración de seguridad o si el archivo .env se ha borrado/movido.

    *Solución: Revisa que el archivo .env esté en su sitio: 
        ls -a para ver archivos ocultos.

**Error: "No space left on device"**
    Si el archivo asturias_update.log o fastapi.log crecen demasiado durante meses.

    *Solución: Vacía los logs.
        true > asturias_update.log
        true > fastapi.log

## 💡 Cómo Automatizar el Inicio (Nivel Pro)
    Si quieres que el Backend se levante solo cada vez que el servidor se reinicie sin que tengas que escribir nada, añade esto a tu crontab -e:

    @reboot /home/erpnext/.services/app_example/venv/bin/python3 -m uvicorn app.main:app --host 0.0.0.0 --port 8000
    La instrucción @reboot es mágica: se ejecuta en cuanto el servidor recibe corriente.
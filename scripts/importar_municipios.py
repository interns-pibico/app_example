import psycopg2
import os
from dotenv import load_dotenv

load_dotenv()

def insertar_municipios_fijos():
    # Lista oficial de los 78 concejos de Asturias
    concejos = [
        "Allande", "Aller", "Amieva", "Avilés", "Belmonte de Miranda", "Bimenes", "Boal", "Cabrales", 
        "Cabranes", "Candamo", "Cangas de Onís", "Cangas del Narcea", "Caravia", "Carreño", "Caso", 
        "Castrillón", "Castropol", "Coaña", "Colunga", "Corvera de Asturias", "Cudillero", "Degaña", 
        "El Franco", "Gijón", "Gozón", "Grado", "Grandas de Salime", "Ibias", "Illano", "Illas", 
        "Langreo", "Laviana", "Lena", "Llanera", "Llanes", "Mieres", "Morcín", "Muros de Nalón", 
        "Nava", "Navia", "Noreña", "Onís", "Oviedo", "Parres", "Peñamellera Alta", "Peñamellera Baja", 
        "Pesoz", "Piloña", "Ponga", "Pravia", "Proaza", "Quirós", "Regueras, Las", "Ribadedeva", 
        "Ribadesella", "Ribera de Arriba", "Riosa", "Salas", "San Martín de Oscos", 
        "San Martín del Rey Aurelio", "San Tirso de Abres", "Santa Eulalia de Oscos", "Santo Adriano", 
        "Sariego", "Siero", "Sobrescobio", "Somiedo", "Soto del Barco", "Tapia de Casariego", "Taramundi", 
        "Teverga", "Tineo", "Valdés", "Vegadeo", "Villanueva de Oscos", "Villaviciosa", "Villayón", "Yernes y Tameza"
    ]

    try:
        conn = psycopg2.connect(
            dbname=os.getenv("DB_NAME"),
            user=os.getenv("DB_USER"),
            password=os.getenv("DB_PASS"),
            host=os.getenv("DB_HOST")
        )
        cur = conn.cursor()
        
        print(f"⌛ Insertando {len(concejos)} concejos en la base de datos...")
        
        for nombre in concejos:
            cur.execute("INSERT INTO municipios (nombre) VALUES (%s) ON CONFLICT (nombre) DO NOTHING", (nombre,))
        
        conn.commit()
        
        # Verificación final
        cur.execute("SELECT count(*) FROM municipios")
        total = cur.fetchone()[0]
        
        print(f"✅ ¡Hecho! Ahora tienes {total} municipios en la tabla.")
        
        cur.close()
        conn.close()

    except Exception as e:
        print(f"❌ Error al conectar a la base de datos: {e}")

if __name__ == "__main__":
    insertar_municipios_fijos()
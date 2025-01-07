import requests
import os
import time
import json
import openai
import re
import io

def RAG_CODA(coda_token, coda_document, openai_client, vector_store_id):
    # URL de la API de Coda para obtener los documentos
    url = "https://coda.io/apis/v1/docs"

    # Cabecera con el token de autorización
    headers = {
        "Authorization": f"Bearer {coda_token}"
    }

    # Realizar la solicitud GET a la API de Coda para obtener los documentos
    response = requests.get(url, headers=headers)
    documents = response.json().get("items", [])

    # Buscar el documento
    document_id = None
    for doc in documents:
        if doc.get("name") == coda_document:
            document_id = doc.get("id")
            break

    # Accede a la metadata de los archivos vectorizados y almacenados en el Vector Store
    vs = openai_client.beta.vector_stores.files.list(
        vector_store_id=vector_store_id
        )

    # Almacenamos la metadata
    files = vs.data

    # Revisamos si hay otros documentos en el Vector Store
    while vs.has_more:
        vs = openai_client.beta.vector_stores.files.list(
            vector_store_id=vector_store_id,
            after=vs.last_id
        )
        # Se agregan estos documentos a la variable con metadata
        files += vs.data

    # Inicializamos una variable que almacenará los nuevos FOs para cada archivo
    file_batch = []

    # Eliminamos la versión actual de los archivos en el Vector Store para evitar duplicados o problemas de versionamiento
    for f in files:
        openai_client.files.delete(f.id)

    # Realizar la solicitud GET para obtener las páginas (secciones) del documento
    response = requests.get(f"{url}/{document_id}/pages", headers=headers)

    if response.status_code == 200:
        pages = response.json().get("items", [])
        for pagina in pages:
            page_id = pagina.get('id')
            page_name = pagina.get('name')

            # Solicitud para exportar el archivo como texto.
            uri = f"{url}/{document_id}/pages/{page_id}/export"
            payload = {
                'outputFormat': 'markdown',
                }
            response = requests.post(uri, headers=headers, json=payload)

            try:
                # Revisión del estado de solicitud.
                response = response.json()
                export_status_uri = f"{url}/{document_id}/pages/{page_id}/export/{response['id']}"
                export_status_res = requests.get(export_status_uri, headers=headers).json()
                
                while len(export_status_res) < 4:
                    time.sleep(1)
                    export_status_res = requests.get(export_status_uri, headers=headers).json()

                file_url = export_status_res['downloadLink']
                content = requests.get(file_url).text

                words = re.findall('[a-zA-Z]+', content) # Buscamos la existencia de contenido en el texto
                if (len(words) > 20):
                    file_obj = io.BytesIO(content.encode('utf-8')) # Generación de 'File-Like object'
                    file_obj.name = f"{page_name}.md"
                    file_batch.append(openai_client.files.create(file=file_obj, purpose='assistants').id)
                    print(f'{page_name} FO ha sido creado.')
                else:
                    print(f'Por su tamaño este archivo ({page_name}) ha sido omitido.')
            except:
                print(f"Error al obtener contenido de la página {page_id}: {response.status_code} - {response.text}")
    else:
        print(f"Error al obtener páginas: {response.status_code} - {response.text}")

    if file_batch:
        vector_store_file_batch = openai_client.beta.vector_stores.file_batches.create(
            vector_store_id=vector_store_id,
            file_ids=file_batch
        )
        status = openai_client.beta.vector_stores.file_batches.retrieve(
            vector_store_id=vector_store_id,
            batch_id=vector_store_file_batch.id
        )
        while status.status != 'completed':
            status = openai_client.beta.vector_stores.file_batches.retrieve(
            vector_store_id=vector_store_id,
            batch_id=vector_store_file_batch.id
            )
        print('Batch completo.')
    else:
        print('No hay archivos que agregar.')
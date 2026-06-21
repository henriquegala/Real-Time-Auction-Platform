FROM nginx:alpine

# Remove os arquivos estáticos padrão do Nginx
RUN rm -rf /usr/share/nginx/html/*

# Copia os arquivos do frontend para o diretório público do Nginx
COPY ./index.html /usr/share/nginx/html/index.html
COPY ./app.js /usr/share/nginx/html/app.js

# Copia a configuração personalizada do Nginx
COPY ./nginx.conf /etc/nginx/conf.d/default.conf

# Expõe a porta interna do container
EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
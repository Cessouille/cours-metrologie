FROM docker.elastic.co/logstash/logstash:8.19.16

# Remove default configurations to avoid pipeline conflicts
RUN rm -f /usr/share/logstash/pipeline/logstash.conf

# Copy custom pipeline configuration and dataset file
COPY air-quality-importer/logstash.conf /usr/share/logstash/pipeline/logstash.conf
COPY datasets/Air_Quality.log /usr/share/logstash/Air_Quality.log

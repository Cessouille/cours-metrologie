# TP Observabilité - Prometheus & Grafana

> Célian CHAUSSON

Ce projet implémente une chaîne complète d'observabilité (déploiement, collecte de métriques, visualisation et alertes) pour une application HTTP de type microservice dans un cluster Kubernetes (`kind`), sans utiliser Helm ou Prometheus Operator.

---

## Déploiement

```bash
# Créer le cluster Kind (l'image est spécifiée pour que je puisse run sur mon Windows)
kind create cluster --name tp-monitoring --image kindest/node:v1.31.2 --config kind-config.yaml

# Construire l'image de l'application
docker build -t demo-app:v1.0.0 app

# Charger l'image dans le cluster Kind
kind load docker-image demo-app:v1.0.0 --name tp-monitoring

# Appliquer les manifestes
kubectl apply -f manifests/
```

Vérifier l'état des pods :

```bash
kubectl get pods -A
kubectl get svc -A
```

---

## Organisation des manifests (`manifests/`)

Chaque fichier porte une responsabilité claire, assurant une architecture modulaire et facile à tester :

- **`00-namespaces.yaml`** : Crée les namespaces `monitoring` (composants de métrologie) et `demo` (notre application).
- **`01-demo-app.yaml`** : Déploie notre application Node.js personnalisée dans le namespace `demo`, annotée pour être automatiquement découverte et collectée par Prometheus.
- **`02-node-exporter.yaml`** : Déploie un `DaemonSet` (`prom/node-exporter:v1.11.1`) sur chaque nœud du cluster pour collecter les métriques système du système d'exploitation hôte.
- **`03-kube-state-metrics.yaml`** : Déploie l'image de l'agent de cluster `registry.k8s.io/kube-state-metrics/kube-state-metrics:v2.19.1` avec les droits RBAC associés pour exposer l'état des objets Kubernetes (déploiements, pods, réplicas).
- **`04-alertmanager.yaml`** : Déploie l'image `prom/alertmanager:v0.33.0` avec une configuration minimale de routage d'alertes.
- **`05-prometheus.yaml`** : Configure le RBAC, la `ConfigMap` de configuration et d'alertes, le déploiement (`prom/prometheus:v3.5.3`) et le service pour Prometheus.
- **`06-grafana.yaml`** : Déploie l'image `grafana/grafana:13.0.2` avec ses configurations associées pour auto-provisionner la source de données Prometheus et le tableau de bord. Le tableau de bord est chargé de manière dynamique et non en dur à partir du fichier local `grafana/dashboard.json` grâce à un montage de volume (`extraMounts` dans `kind-config.yaml` et un `hostPath` dans le déploiement de Grafana).

---

## Collecte et découverte automatique (service discovery)

Le TP s'affranchit d'une liste de cibles statiques complexes en utilisant le **kubernetes pod service discovery** dans Prometheus.
Prometheus observe en permanence l'API Kubernetes pour découvrir les nouveaux pods. Il filtre ensuite ces pods pour ne conserver que ceux qui possèdent l'annotation `prometheus.io/scrape: "true"`.

Voici la configuration de relabeling implémentée dans `prometheus.yaml` :

```yaml
scrape_configs:
  - job_name: "kubernetes-pods"
    kubernetes_sd_configs:
      - role: pod
    relabel_configs:
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_scrape]
        action: keep
        regex: "true"
      - source_labels: [__meta_kubernetes_pod_annotation_prometheus_io_path]
        action: replace
        target_label: __metrics_path__
        regex: (.+)
      - source_labels: [__address__, __meta_kubernetes_pod_annotation_prometheus_io_port]
        action: replace
        regex: ([^:]+)(?::\d+)?;(\d+)
        replacement: $1:$2
        target_label: __address__
```

Pour que Prometheus collecte n'importe quel composant, il suffit d'ajouter ces annotations dans la spécification du Pod :

```yaml
metadata:
  annotations:
    prometheus.io/scrape: "true"
    prometheus.io/port: "8080"
    prometheus.io/path: "/metrics"
```

Cette configuration est appliquée sur les pods de **l'application**, de **Prometheus**, d'**Alertmanager**, de **node-exporter**, de **kube-state-metrics** et de **Grafana**. Tous les composants se collectent ainsi automatiquement d'eux-mêmes.

---

## Accès aux interfaces web

Grâce à notre configuration de cluster `kind-config.yaml` et aux services configurés en `NodePort`, les interfaces sont directement accessibles sur la machine locale.

- **Grafana** : [http://localhost:3000](http://localhost:3000) (Identifiants : `admin` / `admin`)
- **Prometheus** : [http://localhost:9090](http://localhost:9090)
- **Alertmanager** : [http://localhost:9093](http://localhost:9093)
- **Application HTTP** : [http://localhost:8080](http://localhost:8080)

## Génération de trafic

Un script Python (`traffic_generator.py`) indépendant de toute bibliothèque tierce (utilise uniquement `urllib` standard) est fourni pour simuler de l'activité utilisateur.

```bash
python traffic_generator.py --url http://localhost:8080 --mode normal
```

Le script supporte d'autres modes indispensables pour tester les alertes (voir section Tests d'alertes ci-dessous).

---

## Choix d'instrumentation de l'application

L'application est une API HTTP Node.js/Express instrumentée avec le SDK officiel `prom-client`.
Elle expose :

1. **Les métriques par défaut de l'environnement d'exécution Node.js** (utilisation CPU, mémoire résidente, lags de l'event loop, cycles du garbage collector).
2. **`http_requests_total`** (Counter) : Nombre de requêtes reçues, labellisées par `method` et `code` HTTP (ex: 200, 404, 500) pour suivre les taux de succès/erreur.
3. **`http_request_duration_seconds`** (Histogram) : Mesure de la latence des requêtes avec des buckets prédéfinis pour le calcul des percentiles de performance (p50, p95).
4. **`demo_app_queue_backlog_size`** (Gauge) : Métrique métier spécifique qui modélise la taille actuelle d'une file de tâches en arrière-plan.

---

## Règles d'alerte et justifications

Les alertes sont configurées dans la ConfigMap `prometheus-config` (définie dans `prometheus.yaml`) et évaluées par Prometheus :

### Alerte 1 : Composant obligatoire indisponible (`ComponentDown`)

- **PromQL** : `(up == 0) or (kube_deployment_status_replicas_available{deployment=~"prometheus|alertmanager|grafana|kube-state-metrics|demo-app"} == 0) or (kube_daemonset_status_number_unavailable{daemonset="node-exporter"} > 0)`
- **Justification** : Détecte l'indisponibilité d'un composant obligatoire sous toutes ses formes. Cette expression robuste combine le scrape Direct de Prometheus (`up == 0`), l'absence de réplicas pour les déploiements applicatifs (`kube_deployment_status_replicas_available == 0`) et les échecs éventuels du DaemonSet système (`kube_daemonset_status_number_unavailable > 0`).

### Alerte 2 : Trop d'erreurs HTTP 5xx (`HighHttp5xxErrorRate`)

- **PromQL** : `sum(increase(http_requests_total{code=~"5.."}[5m])) > 10`
- **Justification** : Se déclenche si l'application produit plus de **`X = 10`** erreurs HTTP de type 500 sur une fenêtre glissante de 5 minutes. Nous choisissons `X = 10` car dans un environnement stable, les erreurs 5xx (erreurs d'infrastructure ou de logique interne) doivent être nulles ou extrêmement isolées. Un cumul de 10 erreurs en 5 minutes indique un bug applicatif persistant ou une panne de dépendance amont.

### Alerte 3 : Alertmanager indisponible dans Kubernetes (`AlertmanagerDeploymentUnavailable`)

- **PromQL** : `kube_deployment_status_replicas_available{deployment="alertmanager", namespace="monitoring"} == 0`
- **Justification** : Cette alerte surveille l'infrastructure Kubernetes via les métriques de `kube-state-metrics`. Elle est totalement indépendante du mécanisme de scrape de Prometheus sur Alertmanager. Si l'orchestrateur signale qu'aucun replica d'Alertmanager n'est disponible dans le cluster, l'alerte se déclenche immédiatement.

### Alerte 4 : Alerte métier de l'application (`DemoAppQueueBacklogTooHigh`)

- **PromQL** : `demo_app_queue_backlog_size > 50`
- **Justification** : Si notre file d'attente de tâches accumule plus de 50 éléments non traités pendant plus d'une minute, cela signifie que notre capacité de traitement en arrière-plan est saturée ou bloquée, menaçant le respect de nos SLAs métier.

---

## Procédures de test des alertes (Validation)

Toutes les alertes ont été rigoureusement testées et validées via l'API Prometheus. Voici comment reproduire ces états :

### Tester l'Alerte 1 : Composant indisponible

1. Arrêtez le service de l'application :

   ```bash
   kubectl scale -n demo deploy/demo-app --replicas=0
   ```

2. Vérifiez que Prometheus signale la cible comme hors-service (`up{app="demo-app"} == 0`). L'alerte passe en état `firing` après 1 minute.

3. Rétablissez le service :

   ```bash
   kubectl scale -n demo deploy/demo-app --replicas=1
   ```

### Tester l'Alerte 2 : Trop d'erreurs HTTP 5xx

1. Déclenchez le générateur de trafic en mode intensif d'erreurs 500 :

   ```bash
   python traffic_generator.py --url http://localhost:8080 --mode high-errors
   ```

2. Après quelques secondes, le volume d'erreurs va exploser. L'alerte `HighHttp5xxErrorRate` se déclenchera.

3. Arrêtez le script et repassez en mode `normal` pour résorber l'alerte.

### Tester l'Alerte 3 : Alertmanager indisponible dans Kubernetes

1. Simulez une panne totale d'Alertmanager au niveau de Kubernetes :

   ```bash
   kubectl scale -n monitoring deploy/alertmanager --replicas=0
   ```

2. Interrogez l'état des alertes dans Prometheus. L'alerte `AlertmanagerDeploymentUnavailable` passera rapidement en état `firing`.

3. Rétablissez Alertmanager :

   ```bash
   kubectl scale -n monitoring deploy/alertmanager --replicas=1
   ```

### Tester l'Alerte 4 : Alerte métier propre à l'application

1. Forcez le gonflement de la file d'attente applicative grâce au générateur :

   ```bash
   python traffic_generator.py --url http://localhost:8080 --mode high-backlog
   ```

2. Le backlog va grimper continuellement au-delà de 50. Après 1 minute dans cet état, l'alerte `DemoAppQueueBacklogTooHigh` passera à l'état `firing`.

3. Pour nettoyer la file et résorber l'alerte, lancez le mode nettoyage :

   ```bash
   python traffic_generator.py --url http://localhost:8080 --mode clear-backlog
   ```

---

## Tableau de bord Grafana

Notre tableau de bord est entièrement auto-provisionné et disponible dès l'ouverture de Grafana. Il est divisé en 5 sections interactives répondant aux exigences du TP :

- **Panel A : Erreurs 5xx (Dernières 5m)** : Panel de type *Stat* affichant le nombre cumulé d'erreurs 5xx sur la fenêtre des 5 dernières minutes. Coloré dynamiquement en rouge dès qu'une erreur apparaît.
- **Panel B : Erreurs 4xx & 5xx (Dernières 5m)** : Panel de type *Stat* affichant le volume total d'erreurs HTTP par code d'erreur (4xx orange, 5xx rouge) sur les 5 dernières minutes.
- **Panel C : Evolution du trafic HTTP par code de réponse** : Graphique temporel (*Time Series*) affichant en temps réel le taux de requêtes par seconde (RPS) de l'application, subdivisé par code de statut (200, 404, 500, etc.).
- **Panel D : Répartition des réponses HTTP (dernières 5m)** : Un diagramme circulaire (*Pie Chart*) affichant la répartition en pourcentage de chaque code HTTP sur les 5 dernières minutes, permettant d'identifier immédiatement le ratio de succès et d'erreurs globales.
- **Panel E : Taille de la file d'attente applicative (queue backlog)** : Graphique temporel (*Time Series*) de notre métrique métier personnalisée `demo_app_queue_backlog_size` qui permet de visualiser directement les oscillations et les saturations de la file d'attente.

---

## Hypothèses ou limites éventuelles

Dans le cadre de ce TP, plusieurs choix de conception et contraintes techniques imposent des limites ou reposent sur des hypothèses spécifiques :

1. **Disponibilité des ports sur la machine hôte :**
   Il est supposé que les ports hôtes configurés dans `kind-config.yaml` (`3000` pour Grafana, `9090` pour Prometheus, `9093` pour Alertmanager, et `8080` pour l'application de démo) sont totalement libres de tout autre service local. Si un autre service utilise l'un de ces ports, l'exposition des services par Kind échouera.

2. **Éphémérité du stockage (données non persistées) :**
   Par souci de simplicité et conformément aux consignes d'un déploiement minimal, tous les composants (Prometheus TSDB, Alertmanager state, Grafana DB interne) utilisent un stockage temporaire de type `emptyDir: {}`. Tout redémarrage de pod ou suppression du cluster détruira l'historique des métriques et l'état des alertes.

3. **Métriques système sous Docker Desktop (Windows/macOS) :**
   `node-exporter` mesure les ressources de la machine sur laquelle il tourne. Puisque le cluster s'exécute dans `kind` au-dessus de Docker Desktop (géré par une VM Linux comme WSL2 sur Windows), les métriques de CPU/mémoire collectées correspondent à cette machine virtuelle sous-jacente et non directement à la machine physique de l'hôte.

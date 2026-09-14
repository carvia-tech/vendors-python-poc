package com.carvia.app;

import imports.k8s.*;
import org.cdk8s.plus27.EnvValue;
import software.constructs.Construct;

import org.cdk8s.App;
import org.cdk8s.Chart;
import org.cdk8s.ChartProps;

import java.util.Collections;
import java.util.List;
import java.util.Map;

public class Main extends Chart {

    public Main(final Construct scope, final String id, WebServiceProps props) {
        this(scope, id, ChartProps.builder().build(), props);
    }

    public Main(final Construct scope, final String id, final ChartProps props, WebServiceProps serviceProps) {
        super(scope, id, props);
        new WebService(this, "backend", serviceProps);

        Map<String, String> label = Collections.singletonMap("app", "celery-worker");
        new KubeDeployment(this, "labinsights-llm-celery-deployment", KubeDeploymentProps.builder()
                .metadata(ObjectMeta.builder().name("labinsights-llm-celery-worker-deployment").build())
                .spec(DeploymentSpec.builder()
                        .replicas(1)
                        .revisionHistoryLimit(2)
                        .selector(LabelSelector.builder()
                                .matchLabels(label)
                                .build())
                        .template(PodTemplateSpec.builder()
                                .metadata(ObjectMeta.builder().labels(label).build())
                                .spec(PodSpec.builder()
                                        .imagePullSecrets(List.of(LocalObjectReference.builder().name("nexus-registry-secret").build()))
                                        .containers(List.of(Container.builder()
                                                .name("celery-worker")
                                                .image(serviceProps.getImage() + ":" + serviceProps.getImageVersion())
                                                .imagePullPolicy("IfNotPresent")
                                                .command(List.of("celery", "-A", "main.celery_app", "worker", "--loglevel=INFO", "--pool=solo", "--concurrency=1"))
                                                .env(List.of(
                                                        EnvVar.builder().name("PYTHONPATH").value("/app/src").build(),
                                                        EnvVar.builder().name("REDIS_HOST").value("redis-service.dev.svc.cluster.local").build(),
                                                        EnvVar.builder().name("REDIS_PORT").value("6379").build(),
                                                        EnvVar.builder().name("DEBUG").value("True").build(),
                                                        EnvVar.builder().name("rabbitmq_host").value("rabbitmq-service.dev.svc.cluster.local").build(),
                                                        EnvVar.builder().name("rabbitmq_port").value("5672").build(),
                                                        EnvVar.builder().name("rabbitmq_username").value("guest").build(),
                                                        EnvVar.builder().name("rabbitmq_password").value("guest").build(),
                                                        EnvVar.builder().name("rabbitmq_queue_name").value("my_queue").build(),
                                                        EnvVar.builder().name("rabbitmq_exchange_name").value("amq.direct").build()
                                                ))
                                                .build()))
                                        .build())
                                .build())
                        .build())
                .build());
    }

    public static void main(String[] args) {
        try {
            final String env = (String) EnvValue.fromProcess("env").getValue();
            final WebServiceProps props = ConfigLoader.load(env);
            props.setImageVersion((String) EnvValue.fromProcess("version").getValue());
            final App app = new App();
            new Main(app, props.getApp().getId(), props);
            app.synth();
        } catch (Exception e) {
            e.printStackTrace();
            throw new RuntimeException(e);
        }
    }
}
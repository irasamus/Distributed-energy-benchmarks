package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;
import com.typesafe.config.*;
import java.time.Duration;
import java.util.Set;

public class AppRunner {

    // 1. DATA TYPES (Must be serializable to move between Node A and Node B)
    public interface MySerializable {}

    public static class SpawnRequest implements MySerializable {
        public final String actorName;
        public final ActorRef<ActorRef<String>> replyTo;

        public SpawnRequest(String actorName, ActorRef<ActorRef<String>> replyTo) {
            this.actorName = actorName;
            this.replyTo = replyTo;
        }
    }

    // 2. THE SPAWNER (This logic runs on Node B)
    public static final ServiceKey<SpawnRequest> SPAWNER_KEY = ServiceKey.create(SpawnRequest.class, "spawner");

    public static Behavior<SpawnRequest> spawnerBehavior() {
        return Behaviors.setup(context -> {
            // Register this node in the cluster so Node A can find it
            context.getSystem().receptionist().tell(Receptionist.register(SPAWNER_KEY, context.getSelf()));
            
            return Behaviors.receive(SpawnRequest.class)
                .onMessage(SpawnRequest.class, msg -> {
                    context.getLog().info("NODE B: Spawning child actor: " + msg.actorName);
                    // Actual spawning happens HERE on Node B
                    ActorRef<String> child = context.spawn(workerBehavior(), msg.actorName);
                    // Reply back to Node A with the reference
                    msg.replyTo.tell(child);
                    return Behaviors.same();
                }).build();
        });
    }

    // 3. THE WORKER (The actor that is actually spawned)
    public static Behavior<String> workerBehavior() {
        return Behaviors.receive((context, msg) -> {
            context.getLog().info("WORKER on Node B received message: " + msg);
            return Behaviors.same();
        });
    }

    // 4. MAIN RUNNER
    public static void main(String[] args) {
        String port = (args.length > 0) ? args[0] : "2551";
        
        // Setup configuration for the cluster nodes
        String configString = 
            "akka.actor.provider = cluster\n" +
            "akka.actor.serialization-bindings { \"" + MySerializable.class.getName() + "\" = jackson-cbor }\n" +
            "akka.remote.artery.canonical.hostname = \"127.0.0.1\"\n" +
            "akka.remote.artery.canonical.port = " + port + "\n" +
            "akka.cluster.seed-nodes = [\"akka://SpawnSystem@127.0.0.1:2551\"]";

        Config config = ConfigFactory.parseString(configString);

        if (port.equals("2551")) {
            // This is Node B: It waits to spawn actors
            ActorSystem.create(spawnerBehavior(), "SpawnSystem", config);
        } else {
            // This is Node A: It initiates the spawn on Node B
            ActorSystem.create(createInitiator(), "SpawnSystem", config);
        }
    }

    public static Behavior<Receptionist.Listing> createInitiator() {
        return Behaviors.setup(context -> {
            // Tell Node A to watch for the Spawner on the network
            context.getSystem().receptionist().tell(Receptionist.subscribe(SPAWNER_KEY, context.getSelf()));

            return Behaviors.receive(Receptionist.Listing.class)
                .onMessage(Receptionist.Listing.class, listing -> {
                    Set<ActorRef<SpawnRequest>> instances = listing.getServiceInstances(SPAWNER_KEY);
                    if (!instances.isEmpty()) {
                        ActorRef<SpawnRequest> remoteSpawner = instances.iterator().next();
                        context.getLog().info("Node A: Found Node B! Sending remote spawn request...");

                        // The 'ask' mimics the GitHub repo's "SpawnProtocol"
                        context.ask(ActorRef.class, remoteSpawner, Duration.ofSeconds(3),
                            replyTo -> new SpawnRequest("energy-actor", (ActorRef) replyTo),
                            (response, throwable) -> {
                                if (response != null) {
                                    ActorRef<String> remoteRef = (ActorRef<String>) response;
                                    remoteRef.tell("Hello from Node A!");
                                }
                                return null;
                            });
                    }
                    return Behaviors.same();
                }).build();
        });
    }
}
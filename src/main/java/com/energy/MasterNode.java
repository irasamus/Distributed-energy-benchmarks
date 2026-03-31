package com.energy;

import akka.actor.*;
import com.typesafe.config.ConfigFactory;

public class MasterNode extends AbstractActor {
    private int count = 0;
    private final int total = 5000;

    @Override
    public void preStart() throws Exception {
        Thread.sleep(2000); // Wait 2 seconds for a strong connection
        System.out.println("LOG_START:" + System.currentTimeMillis());
        
        ActorSelection factory = getContext().actorSelection("akka://RemoteSystem@127.0.0.1:2552/user/factory");
        
        for (int i = 0; i < total; i++) {
            // Send the Master's ActorRef so the Worker knows where to reply
            factory.tell(new WorkerNode.SpawnMe(getSelf()), getSelf());
        }
    }

    @Override
    public Receive createReceive() {
        return receiveBuilder()
            .match(SimpleActor.Done.class, d -> {
                count++;
                if (count % 1000 == 0) System.out.println("Received: " + count);
                if (count == total) {
                    System.out.println("LOG_END:" + System.currentTimeMillis());
                    getContext().getSystem().terminate();
                }
            }).build();
    }

    public static void main(String[] args) {
        String conf = "akka.actor.provider=remote\n" +
                      "akka.remote.artery.canonical.hostname=\"127.0.0.1\"\n" +
                      "akka.remote.artery.canonical.port=2551\n" +
                      "akka.actor.allow-java-serialization=on\n" +
                      "akka.remote.artery.advanced.outbound-message-queue-size=10000";
        
        ActorSystem sys = ActorSystem.create("MasterSystem", ConfigFactory.parseString(conf));
        sys.actorOf(Props.create(MasterNode.class), "master");
    }
}
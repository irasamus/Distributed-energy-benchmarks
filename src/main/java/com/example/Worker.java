package com.example;
import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;

public class Worker {
    public static Behavior<String> create() {
        return Behaviors.receive((context, msg) -> {
            context.getLog().info("WORKER received: " + msg);
            return Behaviors.same();
        });
    }
}
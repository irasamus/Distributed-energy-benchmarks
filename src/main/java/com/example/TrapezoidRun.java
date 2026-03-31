package com.example;

import akka.actor.typed.*;
import akka.actor.typed.javadsl.*;
import akka.actor.typed.receptionist.*;
import com.typesafe.config.*;
import java.time.Duration;
import java.util.*;

public class TrapezoidRun {

    // --- 1. MATHEMATICAL FUNCTION ---
    static double fx(double x) {
        return Math.sin(x) * Math.cos(x) * Math.sqrt(x);
    }

    // --- 2. MESSAGES ---
    public interface TrapezoidSerializable {}

    public static class WorkMessage implements TrapezoidSerializable {
        public double left, right, step;
        public long intervals;
        public ActorRef<ResultMessage> replyTo;

        public WorkMessage() {} // Jackson constructor
        public WorkMessage(double left, double right, double step, long intervals, ActorRef<ResultMessage> replyTo) {
            this.left = left; this.right = right; this.step = step; 
            this.intervals = intervals; this.replyTo = replyTo;
        }
    }

    public static class ResultMessage implements TrapezoidSerializable {
        public double area;
        public ResultMessage() {} // Jackson constructor
        public ResultMessage(double area) { this.area = area; }
    }

    public static final ServiceKey<WorkMessage> WORKER_KEY = ServiceKey.create(WorkMessage.class, "trapezoid-worker");

    // --- 3. WORKER BEHAVIOR (Node B and C) ---
    public static Behavior<WorkMessage> workerBehavior() {
        return Behaviors.setup(context -> {
            // Register this worker in the cluster
            context.getSystem().receptionist().tell(Receptionist.register(WORKER_KEY, context.getSelf()));
            
            return Behaviors.receive(WorkMessage.class)
                .onMessage(WorkMessage.class, msg -> {
                    context.getLog().info("Computing range: " + msg.left + " to " + msg.right);
                    double area = 0.0;
                    double x = msg.left;
                    for (long i = 0; i < msg.intervals; i++) {
                        area += (fx(x) + fx(x + msg.step)) / 2.0 * msg.step;
                        x += msg.step;
                    }
                    msg.replyTo.tell(new ResultMessage(area));
                    return Behaviors.same();
                }).build();
        });
    }

    // --- 4. MASTER BEHAVIOR (Node A) ---
    public static Behavior<Object> masterBehavior(long totalIntervals, int expectedWorkers) {
        return Behaviors.setup(context -> new MasterHandler(context, totalIntervals, expectedWorkers));
    }

    private static class MasterHandler extends AbstractBehavior<Object> {
        private final long totalIntervals;
        private final int expectedWorkers;
        private int workersFinished = 0;
        private double totalArea = 0.0;
        private long startTime;

        public MasterHandler(ActorContext<Object> context, long totalIntervals, int expectedWorkers) {
            super(context);
            this.totalIntervals = totalIntervals;
            this.expectedWorkers = expectedWorkers;
            // Subscribe to find workers
            context.getSystem().receptionist().tell(Receptionist.subscribe(WORKER_KEY, getContext().getSelf().narrow()));
        }

        @Override
        public Receive<Object> createReceive() {
            return newReceiveBuilder()
                .onMessage(Receptionist.Listing.class, listing -> {
                    Set<ActorRef<WorkMessage>> workers = listing.getServiceInstances(WORKER_KEY);
                    if (workers.size() == expectedWorkers && startTime == 0) {
                        startWork(workers);
                    }
                    return this;
                })
                .onMessage(ResultMessage.class, res -> {
                    totalArea += res.area;
                    workersFinished++;
                    if (workersFinished == expectedWorkers) {
                        long end = System.currentTimeMillis();
                        System.out.println("LOG_END:" + end);
                        System.out.println("Result Area: " + totalArea);
                        System.out.println("Total Time: " + (end - startTime) + " ms");
                        return Behaviors.stopped();
                    }
                    return this;
                })
                .build();
        }

        private void startWork(Set<ActorRef<WorkMessage>> workers) {
            System.out.println("Found " + expectedWorkers + " workers. Starting calculation...");
            this.startTime = System.currentTimeMillis();
            System.out.println("LOG_START:" + startTime);

            double leftBoundary = 1.0;
            double rightBoundary = 100.0;
            double step = (rightBoundary - leftBoundary) / totalIntervals;
            long intervalsPerWorker = totalIntervals / expectedWorkers;

            int i = 0;
            for (ActorRef<WorkMessage> worker : workers) {
                double wLeft = leftBoundary + (i * intervalsPerWorker * step);
                double wRight = wLeft + (intervalsPerWorker * step);
                worker.tell(new WorkMessage(wLeft, wRight, step, intervalsPerWorker, getContext().getSelf().narrow()));
                i++;
            }
        }
    }

    // --- 5. MAIN ---
    public static void main(String[] args) {
        String port = (args.length > 0) ? args[0] : "2551";
        long totalIntervals = 1000000000L; // 1 Billion (adjust for your machine)
        int numWorkersExpected = 2; // We wait for 2 remote nodes

        Config config = ConfigFactory.parseString(
            "akka.actor.provider = cluster\n" +
            "akka.actor.serialization-bindings { \"" + TrapezoidSerializable.class.getName() + "\" = jackson-cbor }\n" +
            "akka.remote.artery.canonical.hostname = \"127.0.0.1\"\n" +
            "akka.remote.artery.canonical.port = " + port + "\n" +
            "akka.cluster.seed-nodes = [\"akka://TrapezoidSystem@127.0.0.1:2551\"]"
        );

        if (port.equals("2552")) {
            // NODE A: Master
            ActorSystem.create(masterBehavior(totalIntervals, numWorkersExpected), "TrapezoidSystem", config);
        } else {
            // NODE B or C: Worker
            ActorSystem.create(workerBehavior(), "TrapezoidSystem", config);
            System.out.println("Worker Node UP on port " + port);
        }
    }
}
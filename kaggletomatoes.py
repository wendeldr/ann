import pandas as pd
from collections import Counter
import random
import math
import numpy as np

PAD_INDEX = 0
UNKNOWN_INDEX = 1
# http://neuralnetworksanddeeplearning.com/chap3.html
train = pd.read_csv("data/train.tsv", header=0, delimiter="\t", quoting=3)

num_phrases = train["PhraseId"].size

training_sentiment = []

# Fast Fola suggested this naming convention
def hot_vectorize(sentiment):
    one_hot_vector = [0,0,0,0,0]
    one_hot_vector[sentiment-1]=1
    return one_hot_vector

sentences = []
last_sentence_id = 0
for i in range(0, num_phrases):
    sentence_id = train["SentenceId"][i]
    if sentence_id != last_sentence_id:
        sentences.append(train["Phrase"][i].split())
        last_sentence_id = sentence_id
        training_sentiment.append(hot_vectorize(int(train["Sentiment"][i])))

print("Number of sentences: ", len(sentences))
print(sentences[0:1])

print("Hot vectorized Sentiment is: ", training_sentiment[0:2])

sentence_max = 0
counter = Counter()
for sentence in sentences:
    sentence_max = max(sentence_max, len(sentence))
    for word in sentence:
        counter[word] += 1

print("Sentence max :" + str(sentence_max))
print(len(counter))
print(counter.most_common(10))

i = 2
lookup_table = {}
for word, _ in counter.most_common(18000):
    lookup_table[word] = i
    i += 1

print(lookup_table["the"])

def lookup_word(word):
    if word in lookup_table:
        return lookup_table[word]
    else:
        return UNKNOWN_INDEX
    # return lookup_table[word] if word in lookup_table else UNKNOWN_INDEX

sentence_input = []
for sentence in sentences:
    numeric_words = list(map(lookup_word, sentence))
    numeric_words += [PAD_INDEX] * (sentence_max - len(numeric_words))
    sentence_input.append(numeric_words)

# Hijack the actual sentences and put a linear model in place instead, for testing.

sentence_max = 1
sentence_input = [[x] for x in range(0, 10000)]
training_sentiment = [[x / 10000.0, (10000.0 - x) / 10000.0] for x in range(0, 10000)]

print("sentence_input = ", sentence_input[0:2], "; training_sentiment = ", training_sentiment[0:2])

# print(sentence_input[0:2])

# Build the neural network itself.

def generate_layer(input_size, output_size):
    weights = np.random.random([output_size, input_size])
    biases = np.random.random([output_size])
    return weights, biases

def evaluate_layer(weights, biases, inputs, apply_function):
    return apply_function(np.matmul(weights, inputs) + biases)

def activation_function(layer):
    return map(math.tanh,layer)

def activation_derivative(layer):
    return map(lambda x: 1 - (math.tanh(x)**2), layer)

def transfer_function(layer):
    numerator = map(math.exp, layer)
    denominator = sum(numerator)
    return map(lambda x: x/denominator, numerator)


def cross_entropy(expected, actual):
    error_vector = []
    for i in range(0, len(expected)):
        error_vector.append(expected[i] * math.log(actual[i]))
    return -sum(error_vector)

def derivative_cross_entropy_with_softmax(expected, actual):
    derivative = []
    for i in range(0, len(expected)):
        derivative.append(actual[i] - expected[i])
    return derivative


class Layer:
    # this changed to take an input batch
    def __init__(self, input_batch, weights, biases, activation_derivative):
        self.input_batch = input_batch
        self.weights = weights
        self.biases = biases
        self.activation_derivative = activation_derivative

# Returns an array of (bias_derivatives, weight_derivatives) tuples, one per layer in reverse order.
def bias_weight_layer_derivatives(expected_outputs, actual_outputs, sentence_index, layers):
    derivatives_per_layer = []

    # Compute the initial values of the error, the bias derivatives and weight derivatives for the output layer.
    error = layers[0].activation_derivative(expected_outputs, actual_outputs)
    bias_derivatives = error
    weight_derivatives = np.matmul(np.atleast_2d(error).T, np.atleast_2d(layers[0].input_batch[sentence_index]))
    derivatives_per_layer.append((bias_derivatives, weight_derivatives))

    l = 1
    while l < len(layers):
        previous_error = error  # really the next layer in a feed forward sense
        previous_layer = layers[l - 1]
        layer = layers[l]
        error = np.matmul(previous_layer.weights.T, previous_error)

        # Compute Wx + b (z in the neural networks book)
        wx_b = np.matmul(layer.weights, layer.input_batch[sentence_index]) + layer.biases

        derivative = layer.activation_derivative(wx_b)
        for i in range(0, len(error)):
            error[i] *= derivative[i]

        # Don't judge, we'll clean this up later.  This is totally copied and pasted from the above.

        bias_derivatives = error
        weight_derivatives = np.matmul(np.atleast_2d(error).T, np.atleast_2d(layer.input_batch[sentence_index]))
        derivatives_per_layer.append((bias_derivatives, weight_derivatives))

        l += 1

    return derivatives_per_layer


# Layers is a tuple of (inputs, weights, biases) for each layer.
# layers[0] is the output layer, working backwards from there.
def backprop(expected_output_batch, actual_output_batch, layers, learning_rate = 0.001):
    # Compute partial derivatives for the biases and weights on the output layer.
    # TODO: figure out how to iterate and what args to pass to the function below

    # total_bias_derivatives is an array of bias derivatives, one per layer
    total_bias_derivatives = []
    # total_weight_derivatives is an array of weight derivatives, one per layer
    total_weight_derivatives = []
    for sentence_index in range(0, len(expected_output_batch)):
        bwd = bias_weight_layer_derivatives(expected_output_batch[sentence_index], actual_output_batch[sentence_index], sentence_index, layers)
        # sum this in an accumulator
        for layer_index, layer in enumerate(bwd):
            bias_derivatives, weight_derivatives = layer
            if sentence_index == 0:
                total_bias_derivatives.append(bias_derivatives)
                total_weight_derivatives.append(weight_derivatives)
            else:
                total_bias_derivatives[layer_index] = np.add(total_bias_derivatives[layer_index], bias_derivatives)
                total_weight_derivatives[layer_index] = np.add(total_weight_derivatives[layer_index], weight_derivatives)

    batch_size = float(len(expected_output_batch))

    average_bias_derivatives = map(lambda bd: np.divide(bd, batch_size), total_bias_derivatives)
    average_weight_derivatives = map(lambda wd: np.divide(wd, batch_size), total_weight_derivatives)

    # Apply derivatives to biases and weights in each layer, multiplied by learning rate
    # The learning rate is the fraction by which we are moving down the gradient of the cost function.

    for layer_index, layer in enumerate(layers):
        bias_derivatives = average_bias_derivatives[layer_index]
        weight_derivatives = average_weight_derivatives[layer_index]

        layer.biases -= bias_derivatives * learning_rate
        layer.weights -= weight_derivatives * learning_rate


# Define the network.

# hidden_layer_size = 800
hidden_layer_size = 3
hidden_weights, hidden_biases = generate_layer(sentence_max, hidden_layer_size)

# print(hidden_weights[0:2])

# output_layer_size = 5
output_layer_size = 2
output_weights, output_biases = generate_layer(hidden_layer_size, output_layer_size)

def train_all_sentences(batch_size = 50, num_epochs = 3):
    training_data = zip(sentence_input, training_sentiment)
    for epoch_num in range(0, num_epochs):
        random.shuffle(training_data)
        num_batches = int(math.ceil(len(training_data) / batch_size))
        print("len(training_data) = ", len(training_data), "; batch_size = ", batch_size, "; num_batches = ", num_batches)
        for batch_num in range(0, num_batches):
            batch_start_index = batch_num * batch_size
            batch_end_index = min((batch_num + 1) * batch_size, len(training_data))
            batch = training_data[batch_start_index:batch_end_index]
            
            [sentence_batch, sentiment_batch] = zip(*(batch))

            h1_batch = []
            y_batch = []

            for sentence in sentence_batch:
                # Naming our first hidden layer nodes h1
                # Note to future team : Fast Eric made us do this
                h1 = evaluate_layer(hidden_weights, hidden_biases, sentence, activation_function)
                h1_batch.append(h1)
                y = evaluate_layer(output_weights, output_biases, h1, transfer_function)
                y_batch.append(y)

            hidden_layer = Layer(input_batch = sentence_batch, weights = hidden_weights, biases = hidden_biases, activation_derivative = activation_derivative)
            output_layer = Layer(input_batch = h1_batch, weights = output_weights, biases = output_biases, activation_derivative = derivative_cross_entropy_with_softmax)

            layers = [output_layer, hidden_layer]
        
            backprop(sentiment_batch, y_batch, layers)

            print("Epoch #", epoch_num, ", batch #", batch_num, ", cost = ", cross_entropy(training_sentiment[0], y))


train_all_sentences()


# Next steps: Get this to actually work, then add another hidden layer (h2), then add TensorFlow, then add word2vec.
